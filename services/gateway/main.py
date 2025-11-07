import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import httpx
import redis
import yaml
from fastapi import FastAPI, Header, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from libs.common.models import AgentResult, Provenance, TaskSpec, TaskStatus

app = FastAPI(title="Gateway Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)

PLANNER_URL = os.getenv("PLANNER_URL", "http://planner:8001")
ROUTER_URL = os.getenv("ROUTER_URL", "http://router:8002")
EXECUTOR_URL = os.getenv("EXECUTOR_URL", "http://executor:8003")
VALIDATOR_URL = os.getenv("VALIDATOR_URL", "http://validator:8004")

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True
)

AUTONOMY_CONFIG = {}


def load_autonomy_config():
    global AUTONOMY_CONFIG
    config_path = Path(__file__).parent.parent.parent / "config" / "autonomy.yaml"
    
    if not config_path.exists():
        print(f"Warning: autonomy.yaml not found at {config_path}")
        return
    
    with open(config_path, "r") as f:
        AUTONOMY_CONFIG = yaml.safe_load(f)
    
    print(f"Loaded autonomy config: {AUTONOMY_CONFIG.get('autonomy', {}).get('default_mode')}")


@app.on_event("startup")
async def startup_event():
    load_autonomy_config()


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "gateway"}


async def check_idempotency(idempotency_key: str) -> Optional[dict]:
    """Check if task with this key already exists"""
    cached = redis_client.get(f"idem:{idempotency_key}")
    if cached:
        return json.loads(cached)
    return None


async def store_result(idempotency_key: str, result: dict):
    """Store result for idempotency"""
    redis_client.setex(
        f"idem:{idempotency_key}",
        3600,
        json.dumps(result)
    )


def requires_approval(task: TaskSpec, skill_id: str) -> bool:
    """Check if task requires human approval based on autonomy config"""
    autonomy = AUTONOMY_CONFIG.get("autonomy", {})
    
    skill_overrides = autonomy.get("skill_overrides", {})
    if skill_id in skill_overrides:
        return skill_overrides[skill_id].get("mode") == "approver"
    
    modes = autonomy.get("modes", {})
    mode = task.autonomy_mode.value
    mode_config = modes.get(mode, {})
    
    return not mode_config.get("auto_execute", True)


@app.post("/v1/tasks")
async def create_task(
    task: TaskSpec,
    x_idempotency_key: Optional[str] = Header(None)
):
    start_time = time.time()
    
    task_id = task.task_id or str(uuid4())
    task.task_id = task_id
    
    idempotency_key = x_idempotency_key or hashlib.md5(
        f"{task_id}{task.description}".encode()
    ).hexdigest()
    
    cached = await check_idempotency(idempotency_key)
    if cached:
        return cached
    
    provenance = Provenance(task_id=task_id)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            plan_resp = await client.post(
                f"{PLANNER_URL}/v1/plan",
                json=task.model_dump()
            )
            plan_resp.raise_for_status()
            plan = plan_resp.json()
            
            if not plan.get("steps"):
                raise HTTPException(status_code=400, detail="No execution plan generated")
            
            steps = plan["steps"]
            candidate_skills = [step["skill_id"] for step in steps]
            
            route_resp = await client.post(
                f"{ROUTER_URL}/v1/route",
                json=task.model_dump(),
                params={"candidate_skills": candidate_skills}
            )
            route_resp.raise_for_status()
            routing = route_resp.json()
            
            provenance.router_decision = routing
            
            primary_skill = routing["primary"]["skill_id"]
            
            if requires_approval(task, primary_skill):
                draft_artifact = f"minio://drafts/task_{task_id}_draft.json"
                result = AgentResult(
                    task_id=task_id,
                    status=TaskStatus.AWAITING_APPROVAL,
                    result={"message": "Task requires approval before execution"},
                    provenance=provenance,
                    draft_artifact=draft_artifact
                )
                
                result_dict = result.model_dump()
                await store_result(idempotency_key, result_dict)
                return result_dict
            
            primary_step = next(s for s in steps if s["skill_id"] == primary_skill)
            
            exec_resp = await client.post(
                f"{EXECUTOR_URL}/v1/execute",
                json={"step": primary_step, "task_context": task.context}
            )
            exec_resp.raise_for_status()
            exec_result = exec_resp.json()
            
            provenance.executor_logs.append(exec_result)
            
            val_resp = await client.post(
                f"{VALIDATOR_URL}/v1/validate",
                json={
                    "result": exec_result.get("result", {}),
                    "constraints": task.constraints,
                    "task_type": task.task_type.value
                }
            )
            val_resp.raise_for_status()
            validation = val_resp.json()
            
            provenance.validator_results.append(validation)
            
            if not validation["passed"]:
                alternates = routing.get("alternates", [])
                if alternates:
                    alt_skill = alternates[0]["skill_id"]
                    alt_step = next((s for s in steps if s["skill_id"] == alt_skill), None)
                    
                    if alt_step:
                        exec_resp = await client.post(
                            f"{EXECUTOR_URL}/v1/execute",
                            json={"step": alt_step, "task_context": task.context}
                        )
                        exec_resp.raise_for_status()
                        exec_result = exec_resp.json()
                        
                        provenance.executor_logs.append(exec_result)
                        provenance.retries += 1
            
            latency_ms = (time.time() - start_time) * 1000
            provenance.latency_ms = latency_ms
            provenance.total_cost = routing["primary"]["estimated_cost"]
            provenance.artifacts = exec_result.get("artifacts", [])
            
            audit_artifact = f"minio://audit/task_{task_id}_audit.json"
            provenance.artifacts.append(audit_artifact)
            
            result = AgentResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED if validation["passed"] else TaskStatus.FAILED,
                result=exec_result.get("result"),
                artifacts=exec_result.get("artifacts", []),
                provenance=provenance,
                error=None if validation["passed"] else ", ".join(validation.get("failures", []))
            )
            
            result_dict = result.model_dump()
            await store_result(idempotency_key, result_dict)
            
            return result_dict
            
    except httpx.HTTPError as e:
        error_result = AgentResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            provenance=provenance,
            error=f"Service communication error: {str(e)}"
        )
        
        result_dict = error_result.model_dump()
        await store_result(idempotency_key, result_dict)
        return result_dict


@app.get("/v1/tasks/{task_id}")
async def get_task(task_id: str):
    return {
        "task_id": task_id,
        "status": "completed",
        "message": "Task retrieval not yet implemented"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
