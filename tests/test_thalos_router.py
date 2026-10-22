"""Policy-boundary regressions; synthetic fixtures establish no quality claims."""
import hashlib
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.router import advanced
from services.router.advanced import Constraints, classify_intent, extract_features, rank_agents, rank_models
from services.router.openrouter import _as_model_card, sync_openrouter
from services.router.registries import AGENT_REGISTRY, MODEL_REGISTRY
from services.router.thalos import (
    PROCESSOR_ID, Action, ApprovedAgent, ApprovedDeployment, CallerScope,
    ContextBinding, ResolvedDecision, recommend_for_decision,
)

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)
FUTURE = NOW + timedelta(hours=1)
SCOPE = CallerScope(tenant_id="tenant-a", project_id="project-a", subject_id="user-a")
TEXT = "Fix the failing unit test regression in the auth module"
DIGEST = hashlib.sha256(TEXT.encode()).hexdigest()


@pytest.fixture(autouse=True)
def isolate_catalog(monkeypatch):
    monkeypatch.setattr(advanced, "_EXTRA_MODELS", [])


def model(**changes):
    base = replace(MODEL_REGISTRY[0], model_id="fixture-model", provider="fixture-vendor",
                   cost_in_per_mtok=1, cost_out_per_mtok=1, latency_p50_ms=100,
                   region_hosted=("eu",), compliance=("fixture-control",),
                   catalog_source="fixture_verified_endpoint")
    return replace(base, **changes)


def agent(**changes):
    return replace(AGENT_REGISTRY[1], default_model="fixture-model", fallback_models=(),
                   compliance=("fixture-control",), **changes)


def rank(c, models=None):
    features = extract_features(TEXT)
    return rank_models(features, classify_intent(features), c, models=models or (model(),))


def resolved(**changes):
    values = dict(
        decision_id="decision-a", scope=SCOPE,
        context=ContextBinding(context_id="context-a", profile_version="3",
            profile_snapshot_sha256="a" * 64, policy_version="7",
            policy_snapshot_sha256="b" * 64, resolver_version="1.0.0"),
        valid_until=FUTURE, processing="authorized", permitted_processors=(PROCESSOR_ID,),
        disposition="proceed", actions=(Action(action_id="a1", execution_mode="augment", input_sha256=DIGEST),),
        deployments=(ApprovedDeployment(deployment_id="endpoint-a", evidence_ref="evidence-a",
                                         valid_until=FUTURE, model=model()),),
        agents=(ApprovedAgent(evidence_ref="agent-evidence", valid_until=FUTURE, agent=agent()),),
    )
    values.update(changes)
    return ResolvedDecision(**values)


class Resolver:
    def __init__(self, decision, text=TEXT):
        self.decision, self.text, self.loads = decision, text, []

    def resolve(self, caller, decision_id):
        return self.decision

    def load_action_text(self, caller, decision_id, action_id):
        self.loads.append((caller, decision_id, action_id))
        return self.text


def recommend(decision, text=TEXT):
    resolver = Resolver(decision, text)
    return recommend_for_decision(SCOPE, "decision-a", resolver, now=NOW), resolver


def test_cost_cap_includes_boundary_and_rejects_excess():
    cost = rank(Constraints())[0].projected_cost
    assert rank(Constraints(max_cost_usd=cost))
    assert not rank(Constraints(max_cost_usd=cost / 2))
    assert not rank(Constraints(max_cost_usd=0))


def test_zero_cost_accepts_actually_free_model():
    assert rank(Constraints(max_cost_usd=0), [model(cost_in_per_mtok=0, cost_out_per_mtok=0)])


def test_latency_is_strict_without_fifty_percent_slack():
    assert rank(Constraints(max_latency_ms=100))
    assert not rank(Constraints(max_latency_ms=99))
    assert not rank(Constraints(max_latency_ms=0))


def test_input_and_output_must_fit_even_without_explicit_context_limit():
    assert not rank(Constraints(), [model(context_window=100)])
    assert not rank(Constraints(), [model(max_output=255)])


@pytest.mark.parametrize("kwargs", [
    {"max_cost_usd": -1}, {"max_cost_usd": math.nan}, {"max_cost_usd": math.inf},
    {"max_latency_ms": "100"}, {"max_latency_ms": True}, {"min_context_window": 1.5},
    {"force_tools": "false"}, {"vendor_allowlist": "anthropic"}, {"region": ""},
])
def test_invalid_constraints_fail_closed(kwargs):
    with pytest.raises(ValueError):
        Constraints(**kwargs)


def test_empty_injected_registry_does_not_fall_back_to_global_catalog():
    features = extract_features(TEXT)
    intents = classify_intent(features)
    assert rank_models(features, intents, Constraints(), models=[]) == []
    assert rank_agents(features, intents, [], Constraints(), models=[], agents=[agent()]) == []


def test_agent_compliance_is_elimination_not_a_score_penalty():
    features = extract_features(TEXT)
    bad = replace(agent(), compliance=())
    assert not rank_agents(features, classify_intent(features), [],
                           Constraints(compliance_required=("fixture-control",)),
                           models=[model()], agents=[bad])


def test_agent_primary_and_fallbacks_respect_vendor_restriction():
    features = extract_features(TEXT)
    runner = replace(agent(), default_model="blocked", fallback_models=("fixture-model", "blocked2"))
    candidates = [model(), model(model_id="blocked", provider="other"), model(model_id="blocked2", provider="other")]
    ranked = rank_agents(features, classify_intent(features), [], Constraints(vendor_allowlist=("fixture-vendor",)),
                         models=candidates, agents=[runner])
    assert ranked[0].agent.default_model == "fixture-model"
    assert ranked[0].agent.fallback_models == ()


def test_required_tools_and_agent_overhead_are_enforced():
    features = extract_features(TEXT)
    intents = classify_intent(features)
    assert not rank_agents(features, intents, [], Constraints(required_tools=("unavailable",)),
                           models=[model()], agents=[agent()])
    assert not rank_agents(features, intents, [], Constraints(max_cost_usd=0.01),
                           models=[model()], agents=[replace(agent(), cost_overhead_usd=1)])


@pytest.mark.parametrize("provider", ["anthropic", "amazon", "google", "meta-llama"])
def test_catalog_never_infers_governance_or_free_usage_from_provider(provider):
    card = _as_model_card({"id": f"{provider}/example"})
    assert card.compliance == () and card.region_hosted == ()
    assert not card.open_weights and not card.supports_tools
    assert math.isinf(card.cost_in_per_mtok) and math.isinf(card.latency_p50_ms)
    assert not rank(Constraints(region="eu"), [card])
    assert not rank(Constraints(max_cost_usd=1), [card])
    assert not rank(Constraints(max_latency_ms=10000), [card])


def test_unknown_estimates_serialize_as_null():
    result = rank(Constraints(), [model(cost_in_per_mtok=math.inf, latency_p50_ms=math.inf)])[0].to_dict()
    assert result["projected_cost_usd"] is None
    assert result["projected_latency_ms"] is None
    json.dumps(result, allow_nan=False)


def test_sample_catalog_retains_demo_provenance():
    assert all(c.catalog_source == "openrouter_sample" for c in sync_openrouter(use_sample=True))


def test_catalog_http_serializes_unknown_estimates_and_failure_does_not_install_samples(monkeypatch):
    from services.router.main import app
    from services.router.openrouter import install_into_registry
    install_into_registry([_as_model_card({"id": "fixture/unknown"})])
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic outage")
    monkeypatch.setattr("services.router.openrouter.fetch_openrouter_models", fail)
    with TestClient(app) as client:
        body = client.get("/v2/models").json()
        card = next(m for m in body["models"] if m["model_id"] == "openrouter:fixture/unknown")
        assert card["cost_in_per_mtok"] is None and card["latency_p50_ms"] is None
        assert client.post("/v2/openrouter/sync", json={}).status_code == 502
    assert all(m.catalog_source != "openrouter_sample" for m in advanced.active_models())


@pytest.mark.parametrize("changes, reason", [
    ({"no_ai": True}, "no_ai"),
    ({"processing": "held"}, "processing_not_authorized"),
    ({"processing": "unknown"}, "processing_not_authorized"),
    ({"permitted_processors": ()}, "processor_not_authorized"),
    ({"valid_until": NOW}, "decision_expired"),
])
def test_held_path_never_loads_or_inspects_content(monkeypatch, changes, reason):
    def fail(*args):
        pytest.fail("A held request reached feature extraction")
    monkeypatch.setattr("services.router.thalos.extract_features", fail)
    result, resolver = recommend(resolved(**changes))
    assert result["status"] == "held" and result["reason_code"] == reason
    assert "actions" not in result and "input_sha256" not in json.dumps(result)
    assert result["processing"]["processors_used"] == []
    assert resolver.loads == []


@pytest.mark.parametrize("field", ["tenant_id", "project_id", "subject_id"])
def test_cross_scope_rejected_before_content_load(field):
    bad_scope = CallerScope(**{**SCOPE.model_dump(), field: "another"})
    resolver = Resolver(resolved(scope=bad_scope))
    with pytest.raises(PermissionError):
        recommend_for_decision(SCOPE, "decision-a", resolver, now=NOW)
    assert resolver.loads == []


def test_wrong_decision_reference_is_rejected():
    resolver = Resolver(resolved(decision_id="other-decision"))
    with pytest.raises(PermissionError):
        recommend_for_decision(SCOPE, "decision-a", resolver, now=NOW)
    assert resolver.loads == []


def test_mixed_request_preserves_all_actions_and_authority_checkpoint():
    actions = (
        Action(action_id="a1", execution_mode="automate", input_sha256=DIGEST),
        Action(action_id="a2", execution_mode="augment", input_sha256=DIGEST),
        Action(action_id="a3", execution_mode="automate", authority_bound=True),
        Action(action_id="a4", execution_mode="human"),
    )
    result, resolver = recommend(resolved(actions=actions))
    assert [a["action_id"] for a in result["actions"]] == ["a1", "a2", "a3", "a4"]
    assert [a["execution_mode"] for a in result["actions"]] == ["automate", "augment", "human", "human"]
    assert [entry[2] for entry in resolver.loads] == ["a1", "a2"]
    assert all(not a["model_routes"] and not a["agent_routes"] for a in result["actions"][2:])
    assert result["execution_authorized"] is False


@pytest.mark.parametrize("disposition", ["redirect", "clarify", "defer", "decline"])
def test_non_proceed_dispositions_do_not_load_or_route(disposition):
    result, resolver = recommend(resolved(disposition=disposition))
    assert resolver.loads == []
    assert result["actions"][0]["status"] == "not_routed"


def test_unknown_input_requests_clarification_instead_of_generic_route():
    text = "xyzzy plugh qux"
    action = Action(action_id="a1", execution_mode="augment", input_sha256=hashlib.sha256(text.encode()).hexdigest())
    result, _ = recommend(resolved(actions=(action,)), text)
    assert result["actions"][0]["status"] == "clarify"
    assert result["actions"][0]["model_routes"] == []


def test_input_digest_prevents_routing_a_changed_action():
    with pytest.raises(ValueError, match="snapshot"):
        recommend(resolved(), "replacement content")


def test_oversized_input_is_rejected_without_classification(monkeypatch):
    def fail(*args):
        pytest.fail("Oversized input was classified")
    monkeypatch.setattr("services.router.thalos.extract_features", fail)
    with pytest.raises(ValueError, match="input contract"):
        recommend(resolved(), "x" * 100_001)


def test_expired_and_sample_deployments_never_route():
    expired = ApprovedDeployment(deployment_id="expired", evidence_ref="e1", valid_until=NOW, model=model())
    sample = ApprovedDeployment(deployment_id="sample", evidence_ref="e2", valid_until=FUTURE,
                                model=model(catalog_source="openrouter_sample"))
    result, resolver = recommend(resolved(deployments=(expired, sample)))
    assert result["actions"][0]["status"] == "no_eligible_route"
    assert resolver.loads == []


def test_expired_agent_approval_is_excluded_without_losing_model_route():
    expired = ApprovedAgent(evidence_ref="old", valid_until=NOW, agent=agent())
    result, _ = recommend(resolved(agents=(expired,)))
    assert result["actions"][0]["model_routes"]
    assert result["actions"][0]["agent_routes"] == []


def test_unsatisfied_action_constraints_do_not_restore_global_candidates():
    action = Action(action_id="a1", execution_mode="augment", input_sha256=DIGEST,
                    constraints=Constraints(vendor_allowlist=("unapproved-vendor",)))
    result, _ = recommend(resolved(actions=(action,)))
    assert result["actions"][0]["status"] == "no_eligible_route"
    assert result["actions"][0]["model_routes"] == []


def test_each_mixed_action_keeps_its_own_restrictions():
    actions = (Action(action_id="a1", execution_mode="augment", input_sha256=DIGEST),
               Action(action_id="a2", execution_mode="augment", input_sha256=DIGEST,
                      constraints=Constraints(max_cost_usd=0)))
    result, _ = recommend(resolved(actions=actions))
    assert [a["status"] for a in result["actions"]] == ["recommended", "no_eligible_route"]


def test_tenant_specific_registry_is_used_instead_of_global_models_and_agents():
    result, _ = recommend(resolved())
    action = result["actions"][0]
    assert {r["model_id"] for r in action["model_routes"]} == {"fixture-model"}
    assert action["model_routes"][0]["deployment_id"] == "endpoint-a"
    assert action["agent_routes"][0]["model_deployments"] == {"fixture-model": ["endpoint-a"]}
    assert result["context"]["profile_version"] == "3"
    assert result["context"]["policy_version"] == "7"
    assert TEXT not in json.dumps(result)


def test_agent_deployment_mapping_excludes_over_budget_endpoint():
    expensive = ApprovedDeployment(deployment_id="expensive", evidence_ref="e2", valid_until=FUTURE,
                                    model=model(cost_in_per_mtok=20, cost_out_per_mtok=20))
    decision = resolved()
    action = Action(action_id="a1", execution_mode="augment", input_sha256=DIGEST,
                    constraints=Constraints(max_cost_usd=0.01))
    runner = ApprovedAgent(evidence_ref="agent", valid_until=FUTURE,
                           agent=replace(agent(), cost_overhead_usd=0.005))
    result, _ = recommend(resolved(actions=(action,), deployments=(*decision.deployments, expensive), agents=(runner,)))
    assert result["actions"][0]["agent_routes"][0]["model_deployments"] == {"fixture-model": ["endpoint-a"]}


def test_contract_forbids_unknown_fields_duplicate_actions_and_unbound_inputs():
    with pytest.raises(ValidationError):
        resolved(unrecognized="value")
    action = Action(action_id="same", execution_mode="human")
    with pytest.raises(ValidationError):
        resolved(actions=(action, action))
    with pytest.raises(ValidationError):
        Action(action_id="ai", execution_mode="augment")


@pytest.mark.parametrize("endpoint", ["/v2/route", "/v2/models/rank", "/v2/agents/rank"])
@pytest.mark.parametrize("constraints", [{"max_cost": 0}, {"max_cost_usd": -1}, {"force_tools": "false"}])
def test_http_rejects_invalid_or_misspelled_constraints(endpoint, constraints):
    from services.router.main import app
    with TestClient(app) as client:
        response = client.post(endpoint, json={"text": TEXT, "constraints": constraints})
    assert response.status_code == 422


def test_no_public_endpoint_accepts_a_self_asserted_thalos_authorization():
    from services.router.main import app
    assert not any("thalos" in route.path for route in app.routes)


@pytest.mark.parametrize("endpoint", ["/v2/route", "/v2/models/rank"])
def test_invalid_scoring_weights_are_client_errors(endpoint):
    from services.router.main import app
    with TestClient(app) as client:
        assert client.post(endpoint, json={"text": TEXT, "weights": {"capability": -1}}).status_code == 422


def test_committed_schema_matches_runtime_contract():
    from pathlib import Path
    path = Path(__file__).parents[1] / "docs/thalos-routing-handoff.schema.json"
    assert json.loads(path.read_text()) == ResolvedDecision.model_json_schema()
