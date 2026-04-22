"""Tests for the advanced LLM router."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from services.router.advanced import (
    Constraints,
    classify_intent,
    extract_features,
    infer_skills,
    infer_tools,
    rank_agents,
    rank_models,
    route_request,
)
from services.router.registries import AGENT_REGISTRY, MODEL_REGISTRY
from services.router.taxonomy import INTENTS


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def test_features_detect_modalities():
    feats = extract_features("Please transcribe this voice memo and translate it.")
    assert "audio" in feats.modalities
    assert feats.language == "en"


def test_features_detect_pii():
    feats = extract_features("Contact john@example.com and SSN 123-45-6789")
    assert feats.pii_hits >= 2


def test_features_detect_regulated():
    feats = extract_features("Review this HIPAA clinical summary for the patient")
    assert feats.regulated is True


def test_features_estimate_reasoning():
    shallow = extract_features("hi reply thanks")
    deep = extract_features("Prove and derive the formal theorem via simulation")
    assert deep.estimated_reasoning >= shallow.estimated_reasoning


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

def test_classify_email_intent():
    feats = extract_features("Draft a reply to john@example.com about the inbox update")
    intents = classify_intent(feats)
    assert intents[0].intent.domain == "personal"
    assert "email" in intents[0].intent.intent_id


def test_classify_coding_intent():
    feats = extract_features("Fix the failing unit test regression in the auth module")
    top = classify_intent(feats)[0]
    assert top.intent.vertical == "engineering"


def test_classify_contract_risk_intent():
    feats = extract_features("Flag risky clauses in this MSA contract redline")
    top = classify_intent(feats)[0]
    assert top.intent.intent_id == "biz.ops.contract_risk"
    assert top.intent.regulated is True


def test_classify_falls_back():
    feats = extract_features("xyzzy plugh qux")
    intents = classify_intent(feats)
    assert intents  # never empty


def test_classify_infers_tools_and_skills():
    feats = extract_features("Research this target account and build a competitive battlecard")
    intents = classify_intent(feats)
    tools = infer_tools(feats, intents)
    skills = infer_skills(intents)
    assert "browser" in tools or "serp" in tools
    assert any(s.startswith("SLS-") for s in skills)


# ---------------------------------------------------------------------------
# Model ranking
# ---------------------------------------------------------------------------

def test_rank_models_returns_all_when_no_constraints():
    feats = extract_features("summarize this document")
    intents = classify_intent(feats)
    ranked = rank_models(feats, intents, Constraints())
    assert len(ranked) == len(MODEL_REGISTRY)
    assert ranked[0].score >= ranked[-1].score


def test_rank_models_respects_vendor_allowlist():
    feats = extract_features("draft an email to the team")
    intents = classify_intent(feats)
    c = Constraints(vendor_allowlist=("anthropic",))
    ranked = rank_models(feats, intents, c)
    assert ranked
    assert all(s.model.provider == "anthropic" for s in ranked)


def test_rank_models_respects_compliance():
    feats = extract_features("process this HIPAA clinical record")
    intents = classify_intent(feats)
    c = Constraints(compliance_required=("HIPAA",))
    ranked = rank_models(feats, intents, c)
    assert ranked
    assert all("HIPAA" in s.model.compliance for s in ranked)


def test_rank_models_honors_open_weights():
    feats = extract_features("refactor this Python module")
    intents = classify_intent(feats)
    ranked = rank_models(feats, intents, Constraints(open_weights_only=True))
    assert ranked
    assert all(s.model.open_weights for s in ranked)


def test_rank_models_routes_vision_to_vision_models():
    feats = extract_features("Analyze this screenshot image and extract the table")
    intents = classify_intent(feats)
    ranked = rank_models(feats, intents, Constraints())
    assert "vision" in ranked[0].model.modalities


def test_rank_models_audio_requires_audio_model():
    feats = extract_features("Transcribe the podcast audio recording")
    intents = classify_intent(feats)
    ranked = rank_models(feats, intents, Constraints())
    # text-only models should be filtered because audio is in features.modalities
    assert all("audio" in s.model.modalities for s in ranked)


def test_rank_models_long_context_favoured():
    long_text = "Summarize the following contract. " + ("x " * 80_000)
    feats = extract_features(long_text)
    intents = classify_intent(feats)
    ranked = rank_models(feats, intents, Constraints(min_context_window=500_000))
    assert ranked
    assert all(s.model.context_window >= 500_000 for s in ranked)


# ---------------------------------------------------------------------------
# Agent ranking
# ---------------------------------------------------------------------------

def test_rank_agents_picks_coder_for_code_tasks():
    feats = extract_features("Fix the failing unit test in the auth module")
    intents = classify_intent(feats)
    tools = infer_tools(feats, intents)
    agents = rank_agents(feats, intents, tools, Constraints())
    assert agents[0].agent.agent_id == "quick2.coder"


def test_rank_agents_picks_research_for_prospect():
    feats = extract_features("Research this target account firmographics and buying centers")
    intents = classify_intent(feats)
    tools = infer_tools(feats, intents)
    agents = rank_agents(feats, intents, tools, Constraints())
    assert agents[0].agent.agent_id in {"quick2.sales", "quick2.research"}


def test_rank_agents_picks_exec_assistant_for_schedule():
    feats = extract_features("Book a meeting with Dana next Tuesday at 2pm")
    intents = classify_intent(feats)
    tools = infer_tools(feats, intents)
    agents = rank_agents(feats, intents, tools, Constraints())
    assert agents[0].agent.agent_id == "quick2.exec_assistant"


# ---------------------------------------------------------------------------
# End-to-end routing
# ---------------------------------------------------------------------------

def test_route_request_produces_decision():
    decision = route_request("Draft a proposal for the Siemens BX account")
    assert decision.model_primary is not None
    assert decision.agent_primary is not None
    assert decision.intent_confidence > 0
    assert decision.trace  # has trace entries


def test_route_request_safety_gate_for_pii():
    decision = route_request(
        "Please summarize this record for john@example.com SSN 123-45-6789"
    )
    assert decision.safety_gate["requires_approval"] is True
    assert decision.safety_gate["redaction_required"] is True


def test_route_request_explore_differs_deterministically():
    t = "Plan my week"
    d1 = route_request(t, constraints=Constraints(explore=False))
    d2 = route_request(t, constraints=Constraints(explore=False))
    assert d1.model_primary.model.model_id == d2.model_primary.model.model_id


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from services.router.main import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_http_classify(client):
    r = client.post("/v2/classify", json={"text": "Translate this paragraph to Spanish"})
    assert r.status_code == 200
    body = r.json()
    assert body["top_intents"]
    assert body["top_intents"][0]["domain"] in {"personal", "business"}


def test_http_route(client):
    r = client.post("/v2/route", json={
        "text": "Fix the failing authentication unit test and open a PR",
        "context": {"context_tokens": 20000},
        "constraints": {"max_latency_ms": 5000, "vendor_allowlist": ["anthropic", "openai"]},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["model"]["primary"]["provider"] in {"anthropic", "openai"}
    assert body["agent"]["primary"]["agent_id"] == "quick2.coder"


def test_http_list_models(client):
    r = client.get("/v2/models")
    assert r.status_code == 200
    assert r.json()["count"] == len(MODEL_REGISTRY)


def test_http_list_agents(client):
    r = client.get("/v2/agents")
    assert r.status_code == 200
    assert r.json()["count"] == len(AGENT_REGISTRY)


def test_http_list_taxonomy(client):
    r = client.get("/v2/taxonomy")
    assert r.status_code == 200
    assert r.json()["count"] == len(INTENTS)
