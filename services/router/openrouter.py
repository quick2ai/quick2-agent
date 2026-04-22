"""OpenRouter provider integration.

OpenRouter proxies hundreds of LLMs behind an OpenAI-compatible API.
We treat it as a model-catalog source: fetch `GET /api/v1/models`,
translate each entry into a `ModelCard` (see `registries.py`), infer
a capability vector from provider priors and any benchmark scores we
have, then make those cards available to the router alongside the
hand-curated registry.

The fetch is optional - calling `sync_openrouter(fallback_to_sample=True)`
without a network returns a small built-in sample, which keeps tests
deterministic.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

from .benchmarks import FAMILY_BENCH_SCORES, MODEL_BENCH_SCORES
from .registries import CAPABILITY_AXES, ModelCard


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


# --- Provider priors --------------------------------------------------------
# Used to seed the capability vector when we don't have benchmark data.
# Values are rough quality bands by provider and model tier.

_PROVIDER_PRIORS: Dict[str, Dict[str, float]] = {
    "anthropic": {"reasoning": 0.92, "coding": 0.93, "instruction": 0.94,
                  "safety_alignment": 0.95, "agentic_tool_use": 0.92},
    "openai":    {"reasoning": 0.92, "coding": 0.92, "math": 0.9,
                  "instruction": 0.93, "agentic_tool_use": 0.92},
    "google":    {"reasoning": 0.9, "long_context": 0.95,
                  "multimodal_vision": 0.92, "multimodal_audio": 0.88},
    "meta-llama": {"reasoning": 0.82, "coding": 0.82, "instruction": 0.85,
                   "safety_alignment": 0.83},
    "mistralai": {"reasoning": 0.86, "coding": 0.86, "instruction": 0.9},
    "deepseek":  {"reasoning": 0.9, "coding": 0.92, "math": 0.94,
                  "agentic_tool_use": 0.8},
    "qwen":      {"reasoning": 0.86, "coding": 0.86, "multimodal_vision": 0.85,
                  "multimodal_audio": 0.72},
    "cohere":    {"instruction": 0.9, "factuality": 0.9, "long_context": 0.88},
    "x-ai":      {"reasoning": 0.88, "instruction": 0.87, "speed": 0.7},
    "amazon":    {"instruction": 0.88, "long_context": 0.86,
                  "multimodal_audio": 0.82},
    "nvidia":    {"reasoning": 0.85, "coding": 0.85},
    "microsoft": {"reasoning": 0.84, "coding": 0.85},
    "ai21":      {"instruction": 0.86, "long_context": 0.9},
    "perplexity": {"factuality": 0.9, "instruction": 0.88},
}

_TIER_BASE = {"frontier": 0.9, "balanced": 0.8, "fast": 0.7, "open": 0.78,
              "specialist": 0.7}


def _default_caps() -> Dict[str, float]:
    return {a: 0.55 for a in CAPABILITY_AXES}


def _infer_tier(name: str, cost_out: float, latency_hint: float) -> str:
    n = name.lower()
    # Fast-variant keywords win over the family name ("GPT-5 Mini" is fast).
    if any(k in n for k in ("haiku", "flash", "mini", "nano", "small",
                            "8b", "3b", "1b", "lite", "micro")):
        return "fast"
    if any(k in n for k in ("opus", "ultra", "pro", "large", "max", "405b",
                            "o4", "gpt-5", "claude-4", "405", "r2")):
        return "frontier"
    if any(k in n for k in ("open", "llama", "mixtral", "qwen")):
        return "open"
    if cost_out >= 15:
        return "frontier"
    if cost_out >= 3:
        return "balanced"
    return "fast"


def _infer_family(slug: str) -> str:
    s = slug.lower()
    if "claude" in s:
        return "claude-4" if "-4" in s else "claude-legacy"
    if "gpt-5" in s:
        return "gpt-5"
    if s.startswith("openai/o") or "o3" in s or "o4" in s:
        return "o-series"
    if "gemini" in s:
        return "gemini-2.5" if "2.5" in s else "gemini"
    if "grok" in s:
        return "grok-4"
    if "llama" in s:
        return "llama-4" if "4" in s else "llama"
    if "deepseek" in s:
        return "deepseek-r2" if "r2" in s or "r1" in s else "deepseek"
    if "qwen" in s:
        return "qwen-3" if "3" in s else "qwen"
    if "mistral" in s or "mixtral" in s:
        return "mistral-3"
    if "command" in s:
        return "command-a"
    if "nova" in s:
        return "nova"
    return "other"


def _infer_modalities(architecture: Dict[str, Any]) -> Tuple[str, ...]:
    mods = ["text"]
    raw = architecture or {}
    modality = (raw.get("modality") or raw.get("input_modalities") or "")
    if isinstance(modality, list):
        modality = " ".join(modality)
    modality = modality.lower()
    if "image" in modality or "vision" in modality:
        mods.append("vision")
    if "audio" in modality or "speech" in modality:
        mods.append("audio")
    if "video" in modality:
        mods.append("video")
    return tuple(mods)


def _capabilities_from_priors(provider: str, tier: str,
                              family: str) -> Dict[str, float]:
    base_value = _TIER_BASE.get(tier, 0.75)
    caps = {a: base_value for a in CAPABILITY_AXES}
    caps.update(_PROVIDER_PRIORS.get(provider, {}))
    caps["speed"] = 0.95 if tier == "fast" else 0.6 if tier == "frontier" else 0.8
    # long-context heuristic tuned separately in ModelCard
    # Blend in any family-level benchmark data.
    fam_scores = FAMILY_BENCH_SCORES.get(family)
    if fam_scores:
        if "swe_bench_verified" in fam_scores:
            caps["coding"] = 0.6 * caps["coding"] + 0.4 * fam_scores["swe_bench_verified"]
        if "mmlu_pro" in fam_scores:
            caps["reasoning"] = 0.5 * caps["reasoning"] + 0.5 * fam_scores["mmlu_pro"]
        if "math_500" in fam_scores:
            caps["math"] = 0.4 * caps["math"] + 0.6 * fam_scores["math_500"]
        if "gaia" in fam_scores:
            caps["agentic_tool_use"] = 0.5 * caps["agentic_tool_use"] + 0.5 * fam_scores["gaia"]
        if "longbench_v2" in fam_scores:
            caps["long_context"] = 0.5 * caps["long_context"] + 0.5 * fam_scores["longbench_v2"]
        if "mmmu" in fam_scores:
            caps["multimodal_vision"] = 0.5 * caps["multimodal_vision"] + 0.5 * fam_scores["mmmu"]
        if "truthfulqa" in fam_scores:
            caps["factuality"] = 0.5 * caps["factuality"] + 0.5 * fam_scores["truthfulqa"]
    return {k: round(max(0.0, min(1.0, v)), 3) for k, v in caps.items()}


def _price_per_mtok(p: str) -> float:
    try:
        return float(p) * 1_000_000
    except (TypeError, ValueError):
        return 0.0


def _as_model_card(entry: Dict[str, Any]) -> Optional[ModelCard]:
    slug = entry.get("id") or entry.get("slug")
    if not slug or "/" not in slug:
        return None
    provider, _, _ = slug.partition("/")
    name = entry.get("name", slug)

    pricing = entry.get("pricing", {}) or {}
    cost_in = _price_per_mtok(pricing.get("prompt", 0))
    cost_out = _price_per_mtok(pricing.get("completion", 0))
    ctx = int(entry.get("context_length") or 8_000)
    max_out = int((entry.get("top_provider") or {}).get("max_completion_tokens")
                  or min(ctx // 4, 8_000))

    latency_hint = (entry.get("top_provider") or {}).get("latency_ms", 1500)
    tier = _infer_tier(name, cost_out, latency_hint)
    family = _infer_family(slug)
    caps = _capabilities_from_priors(provider, tier, family)
    mods = _infer_modalities(entry.get("architecture") or {})

    # OpenRouter itself is typically SOC2/GDPR; individual providers vary.
    compliance = ["SOC2", "GDPR"]
    # Heuristic boosts for known compliance-strong providers.
    if provider in ("anthropic", "google", "amazon"):
        compliance.append("HIPAA")
    if provider == "amazon":
        compliance.append("FedRAMP")

    return ModelCard(
        model_id=f"openrouter:{slug}",
        provider=provider,
        family=family,
        tier=tier,
        capabilities=caps,
        cost_in_per_mtok=cost_in,
        cost_out_per_mtok=cost_out,
        latency_p50_ms=float(latency_hint) if latency_hint else 1500.0,
        context_window=ctx,
        max_output=max_out,
        modalities=mods,
        supports_tools=bool(entry.get("supports_tools", True)),
        supports_streaming=True,
        compliance=tuple(compliance),
        region_hosted=("us", "eu"),
        open_weights=provider in ("meta-llama", "mistralai", "qwen",
                                   "deepseek", "nvidia"),
        notes=f"OpenRouter: {slug}",
    )


# ---------------------------------------------------------------------------
# Fetch / cache
# ---------------------------------------------------------------------------

_SAMPLE_MODELS: Tuple[Dict[str, Any], ...] = (
    # A small, realistic sample used when fetch fails or OPENROUTER_FAKE=1.
    {
        "id": "anthropic/claude-opus-4.1", "name": "Claude Opus 4.1",
        "context_length": 1_000_000,
        "pricing": {"prompt": "0.000015", "completion": "0.000075"},
        "architecture": {"modality": "text+image"},
        "top_provider": {"max_completion_tokens": 32000, "latency_ms": 4200},
    },
    {
        "id": "openai/gpt-5", "name": "GPT-5",
        "context_length": 400_000,
        "pricing": {"prompt": "0.00001", "completion": "0.00004"},
        "architecture": {"modality": "text+image+audio"},
        "top_provider": {"max_completion_tokens": 32000, "latency_ms": 3500},
    },
    {
        "id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro",
        "context_length": 2_000_000,
        "pricing": {"prompt": "0.0000035", "completion": "0.000014"},
        "architecture": {"modality": "text+image+audio+video"},
        "top_provider": {"max_completion_tokens": 64000, "latency_ms": 3000},
    },
    {
        "id": "meta-llama/llama-4-70b-instruct", "name": "Llama 4 70B",
        "context_length": 128_000,
        "pricing": {"prompt": "0.00000035", "completion": "0.0000009"},
        "architecture": {"modality": "text+image"},
        "top_provider": {"max_completion_tokens": 8192, "latency_ms": 900},
    },
    {
        "id": "deepseek/deepseek-r2", "name": "DeepSeek R2",
        "context_length": 128_000,
        "pricing": {"prompt": "0.00000055", "completion": "0.0000022"},
        "architecture": {"modality": "text"},
        "top_provider": {"max_completion_tokens": 32000, "latency_ms": 5600},
    },
    {
        "id": "qwen/qwen-3-max", "name": "Qwen 3 Max",
        "context_length": 256_000,
        "pricing": {"prompt": "0.000002", "completion": "0.000006"},
        "architecture": {"modality": "text+image+audio"},
        "top_provider": {"max_completion_tokens": 16000, "latency_ms": 2600},
    },
    {
        "id": "mistralai/mistral-large-3", "name": "Mistral Large 3",
        "context_length": 256_000,
        "pricing": {"prompt": "0.0000025", "completion": "0.0000075"},
        "architecture": {"modality": "text+image"},
        "top_provider": {"max_completion_tokens": 16000, "latency_ms": 1400},
    },
    {
        "id": "cohere/command-a", "name": "Command A",
        "context_length": 256_000,
        "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
        "architecture": {"modality": "text"},
        "top_provider": {"max_completion_tokens": 16000, "latency_ms": 1400},
    },
    {
        "id": "x-ai/grok-4", "name": "Grok 4",
        "context_length": 256_000,
        "pricing": {"prompt": "0.000005", "completion": "0.00002"},
        "architecture": {"modality": "text+image"},
        "top_provider": {"max_completion_tokens": 16000, "latency_ms": 2400},
    },
    {
        "id": "openai/gpt-5-mini", "name": "GPT-5 Mini",
        "context_length": 200_000,
        "pricing": {"prompt": "0.0000006", "completion": "0.0000024"},
        "architecture": {"modality": "text+image+audio"},
        "top_provider": {"max_completion_tokens": 16000, "latency_ms": 600},
    },
    {
        "id": "anthropic/claude-haiku-4.5", "name": "Claude Haiku 4.5",
        "context_length": 200_000,
        "pricing": {"prompt": "0.0000008", "completion": "0.000004"},
        "architecture": {"modality": "text+image"},
        "top_provider": {"max_completion_tokens": 8000, "latency_ms": 700},
    },
    {
        "id": "openai/o4", "name": "o4",
        "context_length": 400_000,
        "pricing": {"prompt": "0.00003", "completion": "0.00012"},
        "architecture": {"modality": "text+image"},
        "top_provider": {"max_completion_tokens": 64000, "latency_ms": 12000},
    },
)


def fetch_openrouter_models(api_key: Optional[str] = None,
                            timeout: float = 10.0,
                            ) -> List[Dict[str, Any]]:
    """Fetch the full OpenRouter model catalog (requires network)."""
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    with httpx.Client(timeout=timeout) as c:
        r = c.get(OPENROUTER_MODELS_URL, headers=headers)
        r.raise_for_status()
        data = r.json()
    return list(data.get("data") or data.get("models") or [])


def sync_openrouter(*,
                    fallback_to_sample: bool = False,
                    use_sample: bool = False,
                    api_key: Optional[str] = None,
                    ) -> List[ModelCard]:
    """Return OpenRouter-backed `ModelCard`s.

    Pass `use_sample=True` (or set `OPENROUTER_FAKE=1`) to skip the
    network and use the embedded sample catalog. Pass
    `fallback_to_sample=True` to gracefully degrade to the sample on
    network error.
    """
    if use_sample or os.getenv("OPENROUTER_FAKE") == "1":
        raw = list(_SAMPLE_MODELS)
    else:
        try:
            raw = fetch_openrouter_models(api_key=api_key)
        except Exception:
            if not fallback_to_sample:
                raise
            raw = list(_SAMPLE_MODELS)

    cards: List[ModelCard] = []
    seen: set = set()
    for entry in raw:
        card = _as_model_card(entry)
        if card is None or card.model_id in seen:
            continue
        seen.add(card.model_id)
        cards.append(card)
    return cards


# ---------------------------------------------------------------------------
# Runtime extension: attaches the fetched cards to the advanced router's
# live model list so ranking includes them immediately.
# ---------------------------------------------------------------------------

def install_into_registry(cards: Iterable[ModelCard]) -> int:
    """Install the given cards into the active router registry.

    Returns the number of *new* cards added (duplicates are merged by id).
    """
    from . import advanced as _adv
    before = {m.model_id for m in _adv.active_models()}
    added = 0
    for card in cards:
        if card.model_id in before:
            continue
        _adv._EXTRA_MODELS.append(card)
        before.add(card.model_id)
        added += 1
    return added
