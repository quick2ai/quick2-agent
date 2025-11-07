import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

app = FastAPI(title="Benchmarks Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True
)

scheduler = AsyncIOScheduler()


def generate_benchmark_data():
    """Generate placeholder benchmark data for Top-15 skills"""
    skills = [
        "COM-001", "COM-002", "OPS-001", "OPS-002", "ENG-001",
        "ENG-002", "CREATIVE-001", "CREATIVE-002", "ANALYSIS-001"
    ]
    
    leaderboard = []
    for skill_id in skills:
        base_p95 = {
            "COM-001": 2800, "COM-002": 2300, "OPS-001": 3800,
            "OPS-002": 4800, "ENG-001": 7500, "ENG-002": 5800,
            "CREATIVE-001": 6800, "CREATIVE-002": 4300, "ANALYSIS-001": 9500
        }.get(skill_id, 5000)
        
        base_cost = {
            "COM-001": 0.02, "COM-002": 0.015, "OPS-001": 0.05,
            "OPS-002": 0.03, "ENG-001": 0.08, "ENG-002": 0.06,
            "CREATIVE-001": 0.04, "CREATIVE-002": 0.025, "ANALYSIS-001": 0.07
        }.get(skill_id, 0.05)
        
        benchmark = {
            "skill_id": skill_id,
            "p95_ms": base_p95 + random.randint(-500, 500),
            "p50_ms": base_p95 * 0.6 + random.randint(-200, 200),
            "success_rate": 0.85 + random.random() * 0.15,
            "cost": base_cost * (0.9 + random.random() * 0.2),
            "total_runs": random.randint(1000, 10000),
            "updated_at": datetime.utcnow().isoformat()
        }
        leaderboard.append(benchmark)
    
    leaderboard.sort(key=lambda x: x["success_rate"] * (1 / (x["p95_ms"] / 1000)), reverse=True)
    
    return leaderboard[:15]


def cache_benchmarks():
    """Cache Top-15 benchmark data in Redis"""
    leaderboard = generate_benchmark_data()
    
    redis_client.set("bench:leaderboard", json.dumps(leaderboard))
    redis_client.set("bench:last_sync", datetime.utcnow().isoformat())
    
    for bench in leaderboard:
        cache_key = f"bench:{bench['skill_id']}"
        redis_client.set(cache_key, json.dumps(bench))
    
    print(f"Cached {len(leaderboard)} benchmarks at {datetime.utcnow().isoformat()}")
    return len(leaderboard)


@app.on_event("startup")
async def startup_event():
    cache_benchmarks()
    
    scheduler.add_job(
        cache_benchmarks,
        'interval',
        minutes=15,
        id='refresh_benchmarks',
        replace_existing=True
    )
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "benchmarks"}


@app.get("/v1/benchmarks/leaderboard")
async def get_leaderboard():
    cached = redis_client.get("bench:leaderboard")
    last_sync = redis_client.get("bench:last_sync")
    
    if cached:
        return {
            "leaderboard": json.loads(cached),
            "last_sync": last_sync,
            "total": len(json.loads(cached))
        }
    
    leaderboard = generate_benchmark_data()
    return {"leaderboard": leaderboard, "total": len(leaderboard)}


@app.post("/v1/benchmarks/sync")
async def sync_benchmarks():
    count = cache_benchmarks()
    return {
        "status": "success",
        "cached_count": count,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/v1/benchmarks/{skill_id}")
async def get_skill_benchmark(skill_id: str):
    cache_key = f"bench:{skill_id}"
    cached = redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    return {"error": "Benchmark not found", "skill_id": skill_id}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8006"))
    uvicorn.run(app, host="0.0.0.0", port=port)
