"""Core engine for the advanced LLM / agent router.

Everything here is dependency-light (stdlib + pydantic) so the router
can run in a unit test without any network calls. Each stage exposes
a clean function so it can be unit-tested or composed separately.

Pipeline:
  preprocess  -> features
  classify    -> top-K intents with confidence
  extract     -> modalities, tools, skills, language, privacy flags
  constrain   -> apply compliance / region / vendor allowlist
  rank_models -> score candidate LLMs per request
  rank_agents -> score candidate agents per request
  decide      -> assemble decision with fallback chain and trace

The routing score is a transparent weighted sum over:
    capability_fit, cost_fit, latency_fit, context_fit,
    reliability, compliance, modality_fit, exploration_bonus
"""
from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .registries import (
    AGENT_REGISTRY,
    AgentCard,
    CAPABILITY_AXES,
    MODEL_REGISTRY,
    ModelCard,
    agents_by_id,
    models_by_id,
)
from .taxonomy import INTENTS, Intent, by_id as intents_by_id
from .benchmarks import benchmark_score_for


# Mutable extension list, written to by openrouter.install_into_registry().
_EXTRA_MODELS: List[ModelCard] = []


def active_models() -> Tuple[ModelCard, ...]:
    """Return the curated registry plus any synced OpenRouter cards."""
    if not _EXTRA_MODELS:
        return tuple(MODEL_REGISTRY)
    return tuple(MODEL_REGISTRY) + tuple(_EXTRA_MODELS)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_\-']+")

_MODALITY_HINTS: Dict[str, Tuple[str, ...]] = {
    "vision":  ("image", "photo", "picture", "chart", "screenshot", "pdf",
                "scan", "diagram", "visual", "ocr"),
    "audio":   ("audio", "voice", "podcast", "call", "meeting recording",
                "transcribe", "voiceover", "tts", "asr"),
    "video":   ("video", "clip", "reel", "youtube", "footage"),
    "tools":   ("call", "fetch", "api", "run", "deploy", "browse",
                "execute", "query the", "book", "schedule"),
}

_REGULATED_HINTS: Tuple[str, ...] = (
    "hipaa", "phi", "ssn", "pii", "credit card", "pci",
    "gdpr", "eu citizen", "data subject", "fedramp", "cjis",
    "clinical", "patient", "medical record", "diagnosis",
    "legal advice", "attorney-client",
)

_PII_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                         # SSN
    re.compile(r"\b\d{16}\b"),                                    # PAN
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),                  # email
    re.compile(r"\b\+?\d[\d \-]{7,14}\d\b"),                      # phone
)

_LANG_HINTS: Dict[str, Tuple[str, ...]] = {
    "es": ("hola", "por favor", "gracias", "cómo", "ayuda", "español"),
    "fr": ("bonjour", "merci", "s'il vous plaît", "aide", "français"),
    "de": ("hallo", "bitte", "danke", "hilfe", "deutsch"),
    "pt": ("olá", "obrigado", "por favor", "ajuda", "português"),
    "ja": ("こんにちは", "ありがとう", "お願い", "日本語"),
    "zh": ("你好", "谢谢", "请", "帮忙", "中文"),
}


@dataclass
class Features:
    text: str
    tokens: List[str]
    length: int
    modalities: List[str]
    language: str
    pii_hits: int
    regulated: bool
    has_code: bool
    has_numbers: bool
    estimated_reasoning: int       # 1..5
    estimated_context_tokens: int


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _WORD.findall(text)]


def _detect_language(text: str, tokens: List[str]) -> str:
    lowered = text.lower()
    for lang, hints in _LANG_HINTS.items():
        if any(h in lowered for h in hints):
            return lang
    return "en"


def _estimate_reasoning(tokens: Sequence[str]) -> int:
    signals = {
        1: ("hi", "hello", "reply"),
        2: ("summarize", "draft", "email", "translate"),
        3: ("analyze", "compare", "recommend", "research"),
        4: ("plan", "architect", "design", "audit", "prove"),
        5: ("optimize", "simulate", "derive", "formal", "theorem"),
    }
    score = 1
    for tier, words in signals.items():
        if any(w in tokens for w in words):
            score = max(score, tier)
    return score


def _estimate_context_tokens(text: str, ctx_hint: int = 0) -> int:
    return max(ctx_hint, int(len(text) / 3.5))


def extract_features(text: str, context: Optional[dict] = None) -> Features:
    ctx = context or {}
    tokens = _tokenize(text)
    lowered = text.lower()

    modalities: List[str] = ["text"]
    for modality, hints in _MODALITY_HINTS.items():
        if any(h in lowered for h in hints):
            modalities.append(modality)
    for m in ctx.get("modalities", []) or []:
        if m not in modalities:
            modalities.append(m)

    regulated = any(h in lowered for h in _REGULATED_HINTS)
    pii_hits = sum(1 for p in _PII_PATTERNS if p.search(text))

    has_code = ("```" in text or bool(re.search(r"\b(def|class|function|import)\b", text)))
    has_numbers = any(c.isdigit() for c in text)

    return Features(
        text=text,
        tokens=tokens,
        length=len(text),
        modalities=modalities,
        language=_detect_language(text, tokens),
        pii_hits=pii_hits,
        regulated=regulated,
        has_code=has_code,
        has_numbers=has_numbers,
        estimated_reasoning=_estimate_reasoning(tokens),
        estimated_context_tokens=_estimate_context_tokens(
            text, int(ctx.get("context_tokens", 0))),
    )


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

@dataclass
class IntentMatch:
    intent: Intent
    score: float
    reasons: List[str]

    def to_dict(self) -> dict:
        return {
            "intent_id": self.intent.intent_id,
            "domain": self.intent.domain,
            "vertical": self.intent.vertical,
            "label": self.intent.label,
            "score": round(self.score, 4),
            "reasons": self.reasons,
        }


def classify_intent(features: Features, top_k: int = 5) -> List[IntentMatch]:
    tokens = set(features.tokens)
    text = features.text.lower()
    matches: List[IntentMatch] = []

    for intent in INTENTS:
        reasons: List[str] = []
        score = 0.0

        kw_hits = sum(1 for k in intent.keywords if k in tokens)
        if kw_hits:
            score += 0.55 * (kw_hits / max(3, len(intent.keywords)))
            reasons.append(f"keywords:{kw_hits}")

        ph_hits = sum(1 for p in intent.phrases if p in text)
        if ph_hits:
            score += 0.35 * min(1.0, ph_hits / max(1, len(intent.phrases)))
            reasons.append(f"phrases:{ph_hits}")

        non_text_intent = set(intent.modalities) - {"text"}
        non_text_feat = set(features.modalities) - {"text"}
        mod_overlap = len(non_text_intent & non_text_feat)
        if mod_overlap:
            score += 0.1 * mod_overlap
            reasons.append(f"modality:{mod_overlap}")

        if features.regulated and intent.regulated:
            score += 0.05
            reasons.append("regulated-match")

        if score > 0:
            matches.append(IntentMatch(intent=intent, score=score, reasons=reasons))

    matches.sort(key=lambda m: m.score, reverse=True)
    if not matches:
        # fall back: best-effort to a generic intent
        default = next(i for i in INTENTS if i.intent_id == "personal.comm.tone")
        matches = [IntentMatch(intent=default, score=0.05, reasons=["fallback"])]
    return matches[:top_k]


def intent_confidence(matches: Sequence[IntentMatch]) -> float:
    """Normalised confidence of the top intent vs. runner-up."""
    if not matches:
        return 0.0
    top = matches[0].score
    if len(matches) == 1 or top == 0:
        return min(1.0, top)
    gap = top - matches[1].score
    return max(0.0, min(1.0, 0.5 + 1.2 * gap))


# ---------------------------------------------------------------------------
# Tool / skill inference
# ---------------------------------------------------------------------------

def infer_tools(features: Features,
                intents: Sequence[IntentMatch]) -> List[str]:
    tools: List[str] = []
    seen = set()
    for m in intents:
        for t in m.intent.tools:
            if t not in seen:
                seen.add(t)
                tools.append(t)
    # Cross-modal inferences
    if "vision" in features.modalities and "pdf_parser" not in seen:
        tools.append("pdf_parser")
    if "audio" in features.modalities and "asr" not in seen:
        tools.append("asr")
    return tools


def infer_skills(intents: Sequence[IntentMatch]) -> List[str]:
    skills: List[str] = []
    seen = set()
    for m in intents:
        for s in m.intent.skills:
            if s not in seen:
                seen.add(s)
                skills.append(s)
    return skills


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

@dataclass
class Constraints:
    max_cost_usd: Optional[float] = None
    max_latency_ms: Optional[float] = None
    min_context_window: Optional[int] = None
    required_modalities: Tuple[str, ...] = ()
    vendor_allowlist: Tuple[str, ...] = ()
    vendor_blocklist: Tuple[str, ...] = ()
    region: Optional[str] = None
    compliance_required: Tuple[str, ...] = ()
    open_weights_only: bool = False
    force_tools: bool = False
    explore: bool = False


def _passes_constraints(model: ModelCard, c: Constraints,
                        features: Features) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if c.vendor_allowlist and model.provider not in c.vendor_allowlist:
        return False, [f"vendor {model.provider} not in allowlist"]
    if model.provider in c.vendor_blocklist:
        return False, [f"vendor {model.provider} is blocked"]
    if c.region and c.region not in model.region_hosted:
        return False, [f"region {c.region} not hosted"]
    for comp in c.compliance_required:
        if comp not in model.compliance:
            return False, [f"missing compliance {comp}"]
    if c.open_weights_only and not model.open_weights:
        return False, ["requires open-weights"]
    for m in c.required_modalities:
        if m not in model.modalities:
            return False, [f"missing modality {m}"]
    for m in features.modalities:
        if m in ("text", "tools"):
            continue
        if m not in model.modalities:
            return False, [f"cannot handle {m}"]
    if "tools" in features.modalities and not model.supports_tools:
        return False, ["tool-use required"]
    if c.min_context_window and model.context_window < c.min_context_window:
        return False, [f"context {model.context_window} < required"]
    if c.force_tools and not model.supports_tools:
        return False, ["tools required but model lacks them"]
    if c.max_latency_ms and model.latency_p50_ms > c.max_latency_ms * 1.5:
        return False, [f"latency {model.latency_p50_ms}ms too high"]
    return True, reasons


# ---------------------------------------------------------------------------
# Model scoring
# ---------------------------------------------------------------------------

@dataclass
class ModelScore:
    model: ModelCard
    score: float
    sub_scores: Dict[str, float]
    projected_cost: float
    projected_latency_ms: float
    reasons: List[str]
    benchmark_score: Optional[float] = None
    benchmark_contributions: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model.model_id,
            "provider": self.model.provider,
            "score": round(self.score, 4),
            "sub_scores": {k: round(v, 4) for k, v in self.sub_scores.items()},
            "projected_cost_usd": round(self.projected_cost, 6),
            "projected_latency_ms": round(self.projected_latency_ms, 1),
            "benchmark_score": (None if self.benchmark_score is None
                                else round(self.benchmark_score, 4)),
            "benchmark_contributions": self.benchmark_contributions,
            "reasons": self.reasons,
        }


# Capability axes relevant to each intent domain, used to weight the
# cosine between the top intent's "need" and the model's "offer".
_DOMAIN_AXES: Dict[str, Dict[str, float]] = {
    "communication":    {"instruction": 1.0, "creative": 0.4, "speed": 0.6},
    "scheduling":       {"instruction": 1.0, "agentic_tool_use": 1.0, "speed": 0.8},
    "productivity":     {"instruction": 0.8, "reasoning": 0.5, "speed": 0.6},
    "finance":          {"reasoning": 1.0, "math": 1.0, "factuality": 1.0},
    "travel":           {"agentic_tool_use": 1.0, "speed": 0.7, "factuality": 0.6},
    "health":           {"factuality": 1.0, "safety_alignment": 1.0, "reasoning": 0.6},
    "home":             {"agentic_tool_use": 1.0, "speed": 1.0},
    "shopping":         {"factuality": 0.8, "reasoning": 0.5, "speed": 0.6},
    "education":        {"reasoning": 0.8, "instruction": 0.9, "creative": 0.4},
    "sales":            {"reasoning": 0.8, "agentic_tool_use": 0.9, "creative": 0.6},
    "marketing":        {"creative": 1.0, "instruction": 0.7},
    "operations":       {"reasoning": 0.9, "long_context": 1.0, "factuality": 0.9},
    "engineering":      {"coding": 1.0, "reasoning": 1.0, "agentic_tool_use": 0.9},
    "data":             {"coding": 0.9, "math": 0.9, "reasoning": 0.9},
    "hr":               {"instruction": 0.8, "creative": 0.5, "safety_alignment": 0.7},
    "legal":            {"reasoning": 1.0, "long_context": 1.0, "factuality": 1.0,
                         "safety_alignment": 0.9},
    "governance":       {"reasoning": 0.9, "factuality": 1.0, "safety_alignment": 1.0},
    "accessibility":    {"instruction": 0.7, "factuality": 0.7},
    "localization":     {"instruction": 0.8, "speed": 0.6},
    "creative":         {"creative": 1.0, "multimodal_vision": 0.5},
    "vertical":         {"reasoning": 0.8, "factuality": 0.8, "long_context": 0.7},
    "system":           {"reasoning": 0.7, "agentic_tool_use": 0.9},
}


def _capability_fit(model: ModelCard, intent: Intent,
                    features: Features,
                    ) -> Tuple[float, Optional[float], Dict[str, float]]:
    """Return (blended fit, benchmark score or None, benchmark contributions)."""
    weights = _DOMAIN_AXES.get(intent.vertical, {"reasoning": 0.6, "instruction": 0.6})
    w_sum = sum(weights.values()) or 1.0
    base = sum(model.capabilities[a] * w for a, w in weights.items()) / w_sum

    # Reasoning-depth bonus: deeper tasks reward stronger reasoning.
    if intent.reasoning_depth >= 4:
        base = 0.5 * base + 0.5 * model.capabilities["reasoning"]
    if intent.agentic:
        base = 0.7 * base + 0.3 * model.capabilities["agentic_tool_use"]
    if intent.long_context or features.estimated_context_tokens > 64_000:
        base = 0.8 * base + 0.2 * model.capabilities["long_context"]
    for mod in features.modalities:
        if mod == "vision":
            base = 0.85 * base + 0.15 * model.capabilities["multimodal_vision"]
        elif mod == "audio":
            base = 0.85 * base + 0.15 * model.capabilities["multimodal_audio"]

    bench_score: Optional[float] = None
    contribs: Dict[str, float] = {}
    lookup = benchmark_score_for(model.model_id, model.family, intent.vertical)
    if lookup is not None:
        bench_score, contribs = lookup
        base = 0.45 * base + 0.55 * bench_score

    return float(max(0.0, min(1.0, base))), bench_score, contribs


def _cost_fit(model: ModelCard, features: Features) -> Tuple[float, float]:
    # Rough projection assuming 4:1 input:output ratio on the requested text.
    in_tok = features.estimated_context_tokens
    out_tok = max(256, in_tok // 4)
    cost = (in_tok * model.cost_in_per_mtok + out_tok * model.cost_out_per_mtok) / 1_000_000
    # Map cost to 0..1 with a soft curve (cheaper = higher).
    fit = 1.0 / (1.0 + cost * 20.0)
    return fit, cost


def _latency_fit(model: ModelCard, c: Constraints) -> float:
    budget = c.max_latency_ms or 10_000.0
    if model.latency_p50_ms <= budget:
        return 1.0 - 0.5 * (model.latency_p50_ms / budget)
    over = (model.latency_p50_ms - budget) / budget
    return max(0.0, 0.5 - 0.5 * over)


def _context_fit(model: ModelCard, features: Features) -> float:
    need = max(4_000, features.estimated_context_tokens)
    if model.context_window >= need * 8:
        return 1.0
    if model.context_window >= need:
        return 0.75 + 0.25 * (model.context_window / (need * 8))
    return max(0.0, model.context_window / need)


def _compliance_fit(model: ModelCard, c: Constraints,
                    regulated: bool) -> float:
    score = 1.0
    if regulated:
        score = min(1.0, 0.4 + 0.15 * len(model.compliance))
    for comp in c.compliance_required:
        if comp not in model.compliance:
            return 0.0
    return score


def _modality_fit(model: ModelCard, features: Features) -> float:
    need = set(features.modalities) - {"text", "tools"}
    if not need:
        return 1.0
    have = set(model.modalities)
    if need.issubset(have):
        return 1.0
    missing = need - have
    return max(0.0, 1.0 - 0.5 * len(missing))


def _exploration_bonus(model: ModelCard, explore: bool,
                       request_hash: int) -> float:
    if not explore:
        return 0.0
    # Hash-based deterministic exploration: spread 0..0.1 across models.
    h = int(hashlib.md5(
        f"{model.model_id}-{request_hash}".encode()).hexdigest()[:8], 16)
    return (h % 1000) / 10_000.0


WEIGHTS: Dict[str, float] = {
    "capability":  0.40,
    "cost":        0.15,
    "latency":     0.10,
    "context":     0.10,
    "compliance":  0.10,
    "modality":    0.10,
    "exploration": 0.05,
}


def rank_models(features: Features,
                intents: Sequence[IntentMatch],
                constraints: Constraints,
                request_hash: int = 0,
                weights: Optional[Dict[str, float]] = None,
                ) -> List[ModelScore]:
    top_intent = intents[0].intent if intents else INTENTS[0]
    w = dict(WEIGHTS)
    if weights:
        w.update(weights)

    ranked: List[ModelScore] = []
    for model in active_models():
        ok, fail_reasons = _passes_constraints(model, constraints, features)
        if not ok:
            continue

        cap, bench_score, contribs = _capability_fit(model, top_intent, features)
        cost_fit, cost = _cost_fit(model, features)
        lat = _latency_fit(model, constraints)
        ctx = _context_fit(model, features)
        comp = _compliance_fit(model, constraints, features.regulated or top_intent.regulated)
        mod = _modality_fit(model, features)
        exp = _exploration_bonus(model, constraints.explore, request_hash)

        sub = {
            "capability": cap, "cost": cost_fit, "latency": lat,
            "context": ctx, "compliance": comp, "modality": mod,
            "exploration": exp,
        }
        total = sum(w[k] * v for k, v in sub.items() if k in w)
        reasons = [f"{k}={v:.2f}" for k, v in sub.items() if v < 0.5]
        if bench_score is not None:
            reasons.insert(0, f"bench={bench_score:.2f}")
        if not reasons:
            reasons = ["balanced fit"]
        ranked.append(ModelScore(
            model=model, score=total, sub_scores=sub,
            projected_cost=cost,
            projected_latency_ms=model.latency_p50_ms,
            reasons=reasons,
            benchmark_score=bench_score,
            benchmark_contributions=contribs,
        ))
    ranked.sort(key=lambda s: s.score, reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Agent scoring
# ---------------------------------------------------------------------------

@dataclass
class AgentScore:
    agent: AgentCard
    score: float
    reasons: List[str]

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent.agent_id,
            "runtime": self.agent.runtime,
            "score": round(self.score, 4),
            "default_model": self.agent.default_model,
            "reasons": self.reasons,
        }


def rank_agents(features: Features,
                intents: Sequence[IntentMatch],
                inferred_tools: Sequence[str],
                constraints: Constraints,
                ) -> List[AgentScore]:
    if not intents:
        return []
    top = intents[0].intent

    # Map intent verticals to the agent most likely to be a strong fit.
    vertical_to_agent = {
        "engineering": "quick2.coder",
        "data": "quick2.analyst",
        "sales": "quick2.sales",
        "marketing": "quick2.creative",
        "creative": "quick2.creative",
        "operations": "quick2.ops",
        "governance": "quick2.safety",
        "legal": "quick2.ops",
        "communication": "quick2.exec_assistant",
        "scheduling": "quick2.exec_assistant",
        "productivity": "quick2.exec_assistant",
        "system": "quick2.router_self",
    }
    preferred = vertical_to_agent.get(top.vertical)

    scored: List[AgentScore] = []
    tool_set = set(inferred_tools)

    for agent in AGENT_REGISTRY:
        reasons: List[str] = []
        score = 0.0

        # Strength keyword match against label/vertical.
        hay = f"{top.label.lower()} {top.vertical}"
        strength_hits = sum(1 for s in agent.strengths if s.lower() in hay)
        if strength_hits:
            score += 0.35 * min(1.0, strength_hits / 2)
            reasons.append(f"strength:{strength_hits}")

        # Tool coverage: fraction of inferred tools the agent supports.
        if tool_set:
            supported = tool_set & set(agent.supported_tools)
            cov = len(supported) / len(tool_set)
            score += 0.30 * cov
            reasons.append(f"tool-cov:{cov:.2f}")
        else:
            score += 0.15

        # Preferred vertical shortcut.
        if preferred and agent.agent_id == preferred:
            score += 0.20
            reasons.append("vertical-preferred")

        # Deep reasoning tasks favour the reasoner agent.
        if top.reasoning_depth >= 5 and agent.agent_id == "quick2.reasoner":
            score += 0.15
            reasons.append("deep-reasoning")

        # Regulated / PII tasks favour the safety agent wrapping the chosen one.
        if features.regulated or features.pii_hits:
            if agent.agent_id == "quick2.safety":
                score += 0.10
                reasons.append("safety-wrap")

        # Penalise wrong autonomy default if the request shape is unclear.
        if top.domain == "personal" and agent.autonomy_default == "approver":
            score -= 0.02

        if constraints.compliance_required and not set(constraints.compliance_required).issubset(set(agent.compliance)):
            # an agent missing compliance is down-weighted but not eliminated;
            # the safety agent will wrap if needed
            score -= 0.05
            reasons.append("compliance-short")

        scored.append(AgentScore(agent=agent, score=max(0.0, score), reasons=reasons))

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Decision assembly
# ---------------------------------------------------------------------------

@dataclass
class RouteTrace:
    stage: str
    at_ms: float
    detail: dict


@dataclass
class RouteDecision:
    request_id: str
    top_intents: List[IntentMatch]
    intent_confidence: float
    features: Features
    tools: List[str]
    skills: List[str]
    model_primary: ModelScore
    model_fallbacks: List[ModelScore]
    agent_primary: Optional[AgentScore]
    agent_fallbacks: List[AgentScore]
    safety_gate: Dict[str, object]
    trace: List[RouteTrace]

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "top_intents": [m.to_dict() for m in self.top_intents],
            "intent_confidence": round(self.intent_confidence, 4),
            "features": {
                "language": self.features.language,
                "modalities": self.features.modalities,
                "pii_hits": self.features.pii_hits,
                "regulated": self.features.regulated,
                "estimated_reasoning": self.features.estimated_reasoning,
                "estimated_context_tokens": self.features.estimated_context_tokens,
            },
            "tools": self.tools,
            "skills": self.skills,
            "model": {
                "primary": self.model_primary.to_dict(),
                "fallbacks": [m.to_dict() for m in self.model_fallbacks],
            },
            "agent": {
                "primary": self.agent_primary.to_dict() if self.agent_primary else None,
                "fallbacks": [a.to_dict() for a in self.agent_fallbacks],
            },
            "safety_gate": self.safety_gate,
            "trace": [{"stage": t.stage, "at_ms": t.at_ms, "detail": t.detail}
                      for t in self.trace],
        }


def _safety_gate(features: Features, intent: Intent) -> Dict[str, object]:
    flags: List[str] = []
    if features.pii_hits:
        flags.append("pii-detected")
    if features.regulated or intent.regulated:
        flags.append("regulated-domain")
    requires_approval = bool(flags) or intent.safety == "regulated"
    return {
        "flags": flags,
        "requires_approval": requires_approval,
        "recommended_autonomy": "approver" if requires_approval else "collaborator",
        "redaction_required": features.pii_hits > 0,
        "audit_required": bool(flags),
    }


def route_request(text: str,
                  context: Optional[dict] = None,
                  constraints: Optional[Constraints] = None,
                  weights: Optional[Dict[str, float]] = None,
                  ) -> RouteDecision:
    t0 = time.time()
    ctx = context or {}
    c = constraints or Constraints()
    trace: List[RouteTrace] = []

    def tick(stage: str, detail: dict) -> None:
        trace.append(RouteTrace(stage=stage,
                                at_ms=round((time.time() - t0) * 1000, 2),
                                detail=detail))

    feats = extract_features(text, ctx)
    tick("features", {
        "language": feats.language,
        "modalities": feats.modalities,
        "pii_hits": feats.pii_hits,
        "regulated": feats.regulated,
    })

    intents = classify_intent(feats)
    tick("classify", {"top": intents[0].intent.intent_id,
                      "confidence": round(intent_confidence(intents), 3)})

    tools = infer_tools(feats, intents)
    skills = infer_skills(intents)
    tick("infer", {"tools": tools, "skills": skills})

    rh = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
    ranked = rank_models(feats, intents, c, request_hash=rh, weights=weights)
    if not ranked:
        raise ValueError("No model satisfies the given constraints")
    tick("rank_models", {
        "primary": ranked[0].model.model_id,
        "considered": len(ranked),
    })

    agents = rank_agents(feats, intents, tools, c)
    tick("rank_agents", {
        "primary": agents[0].agent.agent_id if agents else None,
    })

    safety = _safety_gate(feats, intents[0].intent)
    tick("safety", safety)

    request_id = hashlib.sha1(
        f"{text}-{int(time.time() * 1000)}".encode()).hexdigest()[:16]

    return RouteDecision(
        request_id=request_id,
        top_intents=intents,
        intent_confidence=intent_confidence(intents),
        features=feats,
        tools=tools,
        skills=skills,
        model_primary=ranked[0],
        model_fallbacks=ranked[1:4],
        agent_primary=agents[0] if agents else None,
        agent_fallbacks=agents[1:3],
        safety_gate=safety,
        trace=trace,
    )
