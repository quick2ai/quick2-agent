import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import redis
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

app = FastAPI(title="Dashboard Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True
)


def get_mock_metrics():
    """Generate mock dashboard metrics"""
    now = datetime.utcnow()
    
    task_stream = []
    for i in range(20):
        task_stream.append({
            "task_id": f"task-{1000 + i}",
            "type": random.choice(["COM", "OPS", "ENG", "CREATIVE", "ANALYSIS"]),
            "status": random.choice(["completed", "completed", "completed", "failed", "pending"]),
            "timestamp": (now - timedelta(minutes=i * 5)).isoformat(),
            "latency_ms": random.randint(1000, 10000)
        })
    
    return {
        "task_stream": task_stream,
        "success_rate": 0.87,
        "p50_latency_ms": 3200,
        "p95_latency_ms": 7800,
        "cost_per_task": 0.045,
        "fallback_rate": 0.12,
        "total_tasks_today": 247,
        "active_tasks": 3
    }


def get_skill_roi():
    """Calculate per-skill ROI metrics"""
    skills = ["COM-001", "COM-002", "OPS-001", "OPS-002", "ENG-001", 
              "ENG-002", "CREATIVE-001", "CREATIVE-002", "ANALYSIS-001"]
    
    roi_data = []
    for skill_id in skills:
        roi_data.append({
            "skill_id": skill_id,
            "total_runs": random.randint(20, 200),
            "success_rate": 0.80 + random.random() * 0.19,
            "avg_latency_ms": random.randint(2000, 9000),
            "total_cost": round(random.random() * 50, 2),
            "roi_score": round(random.random() * 100, 1)
        })
    
    roi_data.sort(key=lambda x: x["roi_score"], reverse=True)
    return roi_data


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "dashboard"}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    metrics = get_mock_metrics()
    skill_roi = get_skill_roi()
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "skill_roi": skill_roi,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.get("/api/metrics")
async def get_metrics():
    return get_mock_metrics()


@app.get("/api/skills/roi")
async def get_roi():
    return {"skills": get_skill_roi()}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
