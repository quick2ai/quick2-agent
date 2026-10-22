"""Internal, advisory adapter from a trusted THALOS decision to resource routes.

No HTTP endpoint accepts this authorization envelope. A server-side resolver must
authenticate/access-check the caller, resolve policy and profile snapshots, and
verify deployment/agent evidence before constructing it. This module provides
additional scope/expiry checks; it is not an identity or policy service.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Annotated, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, model_validator

from .advanced import Constraints, classify_intent, extract_features, infer_tools, rank_agents, rank_models
from .registries import AgentCard, ModelCard

ROUTER_VERSION = "2.1.0"
PROCESSOR_ID = "quick2.router.rules/2.1.0"
SCHEMA_VERSION = "0.1.0"
MAX_INPUT_BYTES = 100_000
Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:/-]+$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CallerScope(Contract):
    """Resolved by authentication, never copied from an untrusted request body."""
    tenant_id: Identifier
    project_id: Identifier
    subject_id: Identifier


class ContextBinding(Contract):
    context_id: Identifier
    profile_version: Identifier
    profile_snapshot_sha256: Digest
    policy_version: Identifier
    policy_snapshot_sha256: Digest
    resolver_version: Identifier


class Action(Contract):
    action_id: Identifier
    execution_mode: Literal["automate", "augment", "human"]
    authority_bound: StrictBool = False
    input_sha256: Digest | None = None
    constraints: Constraints = Field(default_factory=Constraints)

    @model_validator(mode="after")
    def bind_input(self):
        if self.execution_mode != "human" and not self.authority_bound and self.input_sha256 is None:
            raise ValueError("AI-assisted actions require an immutable input digest")
        return self


class ApprovedDeployment(Contract):
    """Evidence-backed endpoint snapshot supplied by the trusted resolver.

    model contains the endpoint's verified restrictions and capacity; catalogue
    labels alone must never be used to construct an approval.
    """
    deployment_id: Identifier
    evidence_ref: Identifier
    valid_until: AwareDatetime
    model: ModelCard


class ApprovedAgent(Contract):
    evidence_ref: Identifier
    valid_until: AwareDatetime
    agent: AgentCard


class ResolvedDecision(Contract):
    schema_version: Literal["0.1.0"] = SCHEMA_VERSION
    decision_id: Identifier
    scope: CallerScope
    context: ContextBinding
    valid_until: AwareDatetime
    processing: Literal["authorized", "held", "unknown"]
    no_ai: StrictBool = False
    permitted_processors: tuple[Identifier, ...] = ()
    disposition: Literal["proceed", "redirect", "clarify", "defer", "decline"]
    actions: tuple[Action, ...] = Field(default=(), max_length=32)
    deployments: tuple[ApprovedDeployment, ...] = Field(default=(), max_length=256)
    agents: tuple[ApprovedAgent, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def unique_ids(self):
        for values in (
            [a.action_id for a in self.actions],
            [d.deployment_id for d in self.deployments],
            [a.agent.agent_id for a in self.agents],
        ):
            if len(values) != len(set(values)):
                raise ValueError("Snapshot IDs must be unique within each resource type")
        return self


class DecisionResolver(Protocol):
    def resolve(self, caller: CallerScope, decision_id: str) -> ResolvedDecision:
        """Enforce access; return a pinned, verified decision snapshot."""
        ...

    def load_action_text(self, caller: CallerScope, decision_id: str, action_id: str) -> str:
        """Enforce access again; retrieve only this action's authorized input."""
        ...


def recommend_for_decision(
    caller: CallerScope, decision_id: str, resolver: DecisionResolver,
    *, now: datetime | None = None,
) -> dict:
    """Produce resource suggestions without dispatch, content logging or caching.

    The caller and resolver are trusted application dependencies, not user JSON.
    A hold never loads input or returns actions. Human-only actions also avoid
    input loading. Every AI action is classified and routed independently.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    resolved = resolver.resolve(caller, decision_id)
    if resolved.scope != caller or resolved.decision_id != decision_id:
        raise PermissionError("Decision is unavailable in the caller scope")

    result = {
        "schema_version": SCHEMA_VERSION,
        "decision_id": decision_id,
        "scope": caller.model_dump(),
        "context": resolved.context.model_dump(),
        "router_version": ROUTER_VERSION,
        "classifier_method": "keyword_phrase_rules",
        "calibration_version": None,
        "benchmark_evidence": "unverified_static_snapshot",
        "valid_until": resolved.valid_until.isoformat(),
        "advisory_only": True,
        "execution_authorized": False,
        "processing": {"status": "held", "processors_used": []},
    }
    reason = None
    if resolved.valid_until <= now:
        reason = "decision_expired"
    elif resolved.no_ai:
        reason = "no_ai"
    elif resolved.processing != "authorized":
        reason = "processing_not_authorized"
    elif PROCESSOR_ID not in resolved.permitted_processors:
        reason = "processor_not_authorized"
    if reason:
        return {**result, "status": "held", "reason_code": reason}

    result["processing"]["status"] = "authorized"
    result["disposition"] = resolved.disposition
    results = []
    for action in resolved.actions:
        item = {
            "action_id": action.action_id,
            "execution_mode": "human" if action.authority_bound else action.execution_mode,
            "authority_bound": action.authority_bound,
            "model_routes": [], "agent_routes": [],
        }
        if resolved.disposition != "proceed":
            results.append({**item, "status": "not_routed", "reason_code": resolved.disposition})
            continue
        if item["execution_mode"] == "human":
            results.append({**item, "status": "human", "reason_code": "human_checkpoint"})
            continue

        # A catalogue or expired approval cannot silently become an execution destination.
        deployments = [d for d in resolved.deployments if d.valid_until > now
                       and d.model.catalog_source != "openrouter_sample"]
        if not deployments:
            results.append({**item, "status": "no_eligible_route", "reason_code": "no_current_deployment"})
            continue
        text = resolver.load_action_text(caller, decision_id, action.action_id)
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ValueError("Action input exceeds the supported input contract")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != action.input_sha256:
            raise ValueError("Action input does not match the decision snapshot")
        features = extract_features(text)
        intents = classify_intent(features)
        result["processing"]["processors_used"] = [PROCESSOR_ID]
        if intents[0].reasons == ["fallback"]:
            results.append({**item, "status": "clarify", "reason_code": "unknown_intent"})
            continue

        scored = []
        for deployment in deployments:
            for score in rank_models(features, intents, action.constraints, models=(deployment.model,)):
                scored.append((score, deployment))
        scored.sort(key=lambda pair: pair[0].score, reverse=True)
        if not scored:
            results.append({**item, "status": "no_eligible_route", "reason_code": "constraints_unsatisfied"})
            continue
        item["model_routes"] = [
            {**score.to_dict(), "deployment_id": deployment.deployment_id,
             "evidence_ref": deployment.evidence_ref,
             "valid_until": min(resolved.valid_until, deployment.valid_until).isoformat(),
             "metadata_status": "resolver_verified_deployment"}
            for score, deployment in scored[:4]
        ]
        # Only resolved agents and the already eligible endpoint models enter ranking.
        approved_agents = [a for a in resolved.agents if a.valid_until > now]
        agents = rank_agents(
            features, intents, infer_tools(features, intents), action.constraints,
            models=tuple(d.model for _, d in scored),
            agents=tuple(a.agent for a in approved_agents),
        )
        evidence = {a.agent.agent_id: a.evidence_ref for a in approved_agents}
        expiries = {a.agent.agent_id: a.valid_until for a in approved_agents}
        for score in agents[:3]:
            model_ids = (score.agent.default_model, *score.agent.fallback_models)
            item["agent_routes"].append({
                **score.to_dict(), "evidence_ref": evidence[score.agent.agent_id],
                "valid_until": min(resolved.valid_until, expiries[score.agent.agent_id]).isoformat(),
                "model_deployments": {
                    model_id: [d.deployment_id for m, d in scored if d.model.model_id == model_id
                               and (action.constraints.max_cost_usd is None or
                                    m.projected_cost + score.agent.cost_overhead_usd <= action.constraints.max_cost_usd)]
                    for model_id in model_ids
                },
            })
        results.append({**item, "status": "recommended"})
    return {**result, "status": "completed", "actions": results}
