import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import redis
from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from libs.common.models import RoutingCandidate, RoutingDecision, TaskSpec

app = FastAPI(title="Router Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "router"}


def get_benchmark_data(skill_id: str) -> dict:
    cache_key = f"bench:{skill_id}"
    cached = redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    default_benchmarks = {
        "COM-001": {"p95_ms": 2800, "success_rate": 0.95, "cost": 0.02},
        "COM-002": {"p95_ms": 2300, "success_rate": 0.97, "cost": 0.015},
        "OPS-001": {"p95_ms": 3800, "success_rate": 0.92, "cost": 0.05},
        "OPS-002": {"p95_ms": 4800, "success_rate": 0.89, "cost": 0.03},
        "ENG-001": {"p95_ms": 7500, "success_rate": 0.88, "cost": 0.08},
        "ENG-002": {"p95_ms": 5800, "success_rate": 0.90, "cost": 0.06},
        "CREATIVE-001": {"p95_ms": 6800, "success_rate": 0.93, "cost": 0.04},
        "CREATIVE-002": {"p95_ms": 4300, "success_rate": 0.94, "cost": 0.025},
        "ANALYSIS-001": {"p95_ms": 9500, "success_rate": 0.91, "cost": 0.07},
    }
    
    return default_benchmarks.get(skill_id, {"p95_ms": 5000, "success_rate": 0.90, "cost": 0.05})


def score_skill(skill_id: str, benchmarks: dict, weights: dict) -> float:
    latency_score = max(0, 1 - (benchmarks["p95_ms"] / 10000))
    success_score = benchmarks["success_rate"]
    cost_score = max(0, 1 - (benchmarks["cost"] / 0.1))
    
    score = (
        weights.get("latency", 0.3) * latency_score +
        weights.get("success", 0.5) * success_score +
        weights.get("cost", 0.2) * cost_score
    )
    return score


@app.post("/v1/route")
async def route_task(task: TaskSpec, candidate_skills: List[str] = None):
    if not candidate_skills:
        raise HTTPException(
            status_code=400,
            detail="candidate_skills required"
        )
    
    weights = task.constraints.get("routing_weights", {
        "latency": 0.3,
        "success": 0.5,
        "cost": 0.2
    })
    
    candidates = []
    for skill_id in candidate_skills:
        benchmarks = get_benchmark_data(skill_id)
        score = score_skill(skill_id, benchmarks, weights)
        
        candidate = RoutingCandidate(
            skill_id=skill_id,
            score=score,
            reasoning=f"Score: {score:.3f} (latency={benchmarks['p95_ms']}ms, "
                      f"success={benchmarks['success_rate']:.2%}, cost=${benchmarks['cost']})",
            estimated_cost=benchmarks["cost"],
            estimated_latency_ms=benchmarks["p95_ms"]
        )
        candidates.append(candidate)
    
    candidates.sort(key=lambda x: x.score, reverse=True)
    
    if not candidates:
        raise HTTPException(status_code=404, detail="No candidates found")
    
    decision = RoutingDecision(
        task_id=task.task_id or "unknown",
        primary=candidates[0],
        alternates=candidates[1:3] if len(candidates) > 1 else [],
        benchmark_snapshot={
            skill.skill_id: get_benchmark_data(skill.skill_id)
            for skill in candidates[:15]
        }
    )
    
    return decision.model_dump()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
