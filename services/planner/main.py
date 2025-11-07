import os
import sys
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from libs.common.models import ExecutionStep, Skill, TaskSpec, TaskType

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(ConsoleSpanExporter())
)

app = FastAPI(title="Planner Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)

SKILLS_REGISTRY: dict[str, Skill] = {}


def load_skills():
    global SKILLS_REGISTRY
    skills_path = Path(__file__).parent.parent.parent / "skills" / "skills.yaml"
    
    if not skills_path.exists():
        print(f"Warning: skills.yaml not found at {skills_path}")
        return
    
    with open(skills_path, "r") as f:
        data = yaml.safe_load(f)
    
    for skill_data in data.get("skills", []):
        skill = Skill(**skill_data)
        SKILLS_REGISTRY[skill.skill_id] = skill
    
    print(f"Loaded {len(SKILLS_REGISTRY)} skills")


@app.on_event("startup")
async def startup_event():
    load_skills()


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "planner"}


@app.get("/v1/skills")
async def get_skills():
    return {
        "skills": [skill.model_dump() for skill in SKILLS_REGISTRY.values()],
        "total": len(SKILLS_REGISTRY)
    }


@app.post("/v1/plan")
async def plan_task(task: TaskSpec):
    if not SKILLS_REGISTRY:
        raise HTTPException(status_code=503, detail="Skills registry not loaded")
    
    matching_skills = [
        skill for skill in SKILLS_REGISTRY.values()
        if task.task_type in skill.task_types and skill.enabled
    ]
    
    if not matching_skills:
        raise HTTPException(
            status_code=404,
            detail=f"No skills found for task type {task.task_type}"
        )
    
    steps = []
    for idx, skill in enumerate(matching_skills[:3]):
        step = ExecutionStep(
            step_id=f"step-{idx+1}",
            skill_id=skill.skill_id,
            description=f"Execute {skill.name}: {skill.description}",
            tool=skill.tools[0] if skill.tools else None,
            params={"task_description": task.description, **task.context},
            dependencies=[] if idx == 0 else [f"step-{idx}"]
        )
        steps.append(step)
    
    return {
        "task_id": task.task_id,
        "steps": [step.model_dump() for step in steps],
        "total_estimated_cost": sum(
            SKILLS_REGISTRY[s.skill_id].cost_per_call for s in steps
        ),
        "total_estimated_latency_ms": max(
            SKILLS_REGISTRY[s.skill_id].slo_p95_ms for s in steps
        )
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
