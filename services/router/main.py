import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import redis
from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from libs.common.models import RoutingCandidate, RoutingDecision, TaskSpec
from services.router.advanced import (
    Constraints,
    active_models,
    rank_agents,
    rank_models,
    classify_intent,
    extract_features,
    infer_skills,
    infer_tools,
    route_request,
)
from services.router.benchmarks import (
    BENCHMARKS,
    MODEL_BENCH_SCORES,
    VERTICAL_BENCH_WEIGHTS,
    top_models_for,
)
from services.router.openrouter import install_into_registry, sync_openrouter
from services.router.registries import (
    AGENT_REGISTRY,
    CAPABILITY_AXES,
    MODEL_REGISTRY,
)
from services.router.taxonomy import INTENTS, group_by_domain, group_by_vertical

app = FastAPI(title="Router Service", version="2.0.0")
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


class AdvancedRouteRequest(BaseModel):
    text: str = Field(..., description="Natural-language request from the user")
    context: Dict[str, Any] = Field(default_factory=dict,
                                    description="Optional context: user_id, modalities, context_tokens, etc.")
    constraints: Dict[str, Any] = Field(default_factory=dict,
                                        description="Hard constraints (cost, latency, region, compliance, vendor)")
    weights: Optional[Dict[str, float]] = Field(
        default=None, description="Override scoring weights (capability, cost, latency, ...).")


def _coerce_constraints(raw: Dict[str, Any]) -> Constraints:
    def _tuple(value):
        if value is None:
            return ()
        if isinstance(value, (list, tuple, set)):
            return tuple(value)
        return (value,)

    return Constraints(
        max_cost_usd=raw.get("max_cost_usd"),
        max_latency_ms=raw.get("max_latency_ms"),
        min_context_window=raw.get("min_context_window"),
        required_modalities=_tuple(raw.get("required_modalities")),
        vendor_allowlist=_tuple(raw.get("vendor_allowlist")),
        vendor_blocklist=_tuple(raw.get("vendor_blocklist")),
        region=raw.get("region"),
        compliance_required=_tuple(raw.get("compliance_required")),
        open_weights_only=bool(raw.get("open_weights_only", False)),
        force_tools=bool(raw.get("force_tools", False)),
        explore=bool(raw.get("explore", False)),
    )


@app.post("/v2/route")
async def route_advanced(req: AdvancedRouteRequest):
    """End-to-end advanced routing: intent, tools, skills, LLM, agent."""
    try:
        decision = route_request(
            req.text,
            context=req.context,
            constraints=_coerce_constraints(req.constraints),
            weights=req.weights,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = decision.to_dict()
    try:
        redis_client.setex(f"route:{decision.request_id}", 3600, json.dumps(payload))
    except Exception:
        pass
    return payload


@app.post("/v2/classify")
async def classify_only(req: AdvancedRouteRequest):
    """Intent classification + feature extraction without model selection."""
    features = extract_features(req.text, req.context)
    intents = classify_intent(features)
    return {
        "features": {
            "language": features.language,
            "modalities": features.modalities,
            "pii_hits": features.pii_hits,
            "regulated": features.regulated,
            "estimated_reasoning": features.estimated_reasoning,
            "estimated_context_tokens": features.estimated_context_tokens,
        },
        "top_intents": [m.to_dict() for m in intents],
        "tools": infer_tools(features, intents),
        "skills": infer_skills(intents),
    }


@app.post("/v2/models/rank")
async def rank_models_endpoint(req: AdvancedRouteRequest):
    """Rank candidate LLMs for the given request without agent selection."""
    features = extract_features(req.text, req.context)
    intents = classify_intent(features)
    ranked = rank_models(
        features, intents, _coerce_constraints(req.constraints),
        weights=req.weights,
    )
    if not ranked:
        raise HTTPException(
            status_code=422,
            detail="No model satisfies the provided constraints",
        )
    return {"ranked": [s.to_dict() for s in ranked]}


@app.post("/v2/agents/rank")
async def rank_agents_endpoint(req: AdvancedRouteRequest):
    """Rank candidate agents (orchestrated runners) for the request."""
    features = extract_features(req.text, req.context)
    intents = classify_intent(features)
    tools = infer_tools(features, intents)
    ranked = rank_agents(features, intents, tools, _coerce_constraints(req.constraints))
    return {"ranked": [s.to_dict() for s in ranked]}


@app.get("/v2/models")
async def list_models():
    models = active_models()
    return {
        "count": len(models),
        "curated_count": len(MODEL_REGISTRY),
        "openrouter_count": len(models) - len(MODEL_REGISTRY),
        "capability_axes": list(CAPABILITY_AXES),
        "models": [
            {
                "model_id": m.model_id,
                "provider": m.provider,
                "family": m.family,
                "tier": m.tier,
                "capabilities": m.capabilities,
                "cost_in_per_mtok": m.cost_in_per_mtok,
                "cost_out_per_mtok": m.cost_out_per_mtok,
                "latency_p50_ms": m.latency_p50_ms,
                "context_window": m.context_window,
                "max_output": m.max_output,
                "modalities": list(m.modalities),
                "supports_tools": m.supports_tools,
                "compliance": list(m.compliance),
                "region_hosted": list(m.region_hosted),
                "open_weights": m.open_weights,
                "notes": m.notes,
            }
            for m in models
        ],
    }


class OpenRouterSyncRequest(BaseModel):
    use_sample: bool = Field(
        default=False,
        description="Use embedded sample catalog instead of hitting the network")
    fallback_to_sample: bool = Field(
        default=True,
        description="Fall back to the sample catalog if the fetch fails")
    api_key: Optional[str] = Field(
        default=None,
        description="Optional OpenRouter API key (else OPENROUTER_API_KEY env)")


@app.post("/v2/openrouter/sync")
async def openrouter_sync(req: OpenRouterSyncRequest):
    """Pull the OpenRouter catalog and install its models into the router.

    Accessible via POST so refreshes are explicit; no network call is
    made until this endpoint is invoked.
    """
    try:
        cards = sync_openrouter(
            use_sample=req.use_sample,
            fallback_to_sample=req.fallback_to_sample,
            api_key=req.api_key,
        )
    except Exception as exc:
        raise HTTPException(status_code=502,
                            detail=f"OpenRouter fetch failed: {exc}") from exc
    added = install_into_registry(cards)
    try:
        redis_client.setex("openrouter:last_sync",
                           3600,
                           json.dumps({"fetched": len(cards), "added": added,
                                       "at": datetime.utcnow().isoformat()}))
    except Exception:
        pass
    return {
        "fetched": len(cards),
        "added": added,
        "active_total": len(active_models()),
    }


@app.get("/v2/benchmarks")
async def list_benchmarks():
    return {
        "benchmarks": [
            {
                "bench_id": b.bench_id,
                "name": b.name,
                "family": b.family,
                "description": b.description,
                "source": b.source,
                "higher_is_better": b.higher_is_better,
            }
            for b in BENCHMARKS
        ],
        "vertical_weights": VERTICAL_BENCH_WEIGHTS,
        "model_scores": MODEL_BENCH_SCORES,
    }


@app.get("/v2/benchmarks/top")
async def benchmarks_top(vertical: str, k: int = 5):
    """Return the top-k models by vertical-weighted benchmark score."""
    ranked = top_models_for(vertical, k=k)
    if not ranked:
        raise HTTPException(status_code=404,
                            detail=f"No benchmark data for vertical '{vertical}'")
    return {"vertical": vertical, "ranked": ranked}


@app.get("/v2/agents")
async def list_agents():
    return {
        "count": len(AGENT_REGISTRY),
        "agents": [
            {
                "agent_id": a.agent_id,
                "runtime": a.runtime,
                "description": a.description,
                "strengths": list(a.strengths),
                "default_model": a.default_model,
                "fallback_models": list(a.fallback_models),
                "supported_tools": list(a.supported_tools),
                "autonomy_default": a.autonomy_default,
                "compliance": list(a.compliance),
                "max_parallel": a.max_parallel,
            }
            for a in AGENT_REGISTRY
        ],
    }


@app.get("/v2/taxonomy")
async def list_taxonomy():
    by_dom = {k: [i.intent_id for i in v] for k, v in group_by_domain().items()}
    by_ver = {k: [i.intent_id for i in v] for k, v in group_by_vertical().items()}
    return {
        "count": len(INTENTS),
        "by_domain": by_dom,
        "by_vertical": by_ver,
        "intents": [
            {
                "intent_id": i.intent_id,
                "domain": i.domain,
                "vertical": i.vertical,
                "label": i.label,
                "modalities": list(i.modalities),
                "tools": list(i.tools),
                "skills": list(i.skills),
                "complexity": i.complexity,
                "reasoning_depth": i.reasoning_depth,
                "regulated": i.regulated,
                "agentic": i.agentic,
                "long_context": i.long_context,
            }
            for i in INTENTS
        ],
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
