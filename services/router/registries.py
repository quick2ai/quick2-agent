"""Model and agent registries for the advanced router.

Each entry carries a capability vector plus cost/latency/compliance
metadata so the router can do multi-criteria optimisation without
calling out to a provider.

Capabilities are normalised 0..1 on these axes:
  reasoning, coding, math, creative, instruction, long_context,
  multimodal_vision, multimodal_audio, agentic_tool_use, speed,
  factuality, safety_alignment

Costs are per 1M tokens (USD) at list price; latency_p50_ms is an
observed median for a ~4k input / 1k output workload.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


CAPABILITY_AXES: Tuple[str, ...] = (
    "reasoning", "coding", "math", "creative", "instruction",
    "long_context", "multimodal_vision", "multimodal_audio",
    "agentic_tool_use", "speed", "factuality", "safety_alignment",
)


@dataclass(frozen=True)
class ModelCard:
    model_id: str
    provider: str
    family: str
    tier: str                           # frontier | balanced | fast | open | specialist
    capabilities: Dict[str, float]
    cost_in_per_mtok: float
    cost_out_per_mtok: float
    latency_p50_ms: float
    context_window: int
    max_output: int
    modalities: Tuple[str, ...]         # text, vision, audio, video
    supports_tools: bool = True
    supports_streaming: bool = True
    compliance: Tuple[str, ...] = ()    # SOC2, HIPAA, GDPR, FedRAMP, ISO27001
    region_hosted: Tuple[str, ...] = ("us", "eu")
    open_weights: bool = False
    notes: str = ""


def _caps(**kw) -> Dict[str, float]:
    base = {a: 0.5 for a in CAPABILITY_AXES}
    base.update(kw)
    return base


MODEL_REGISTRY: Tuple[ModelCard, ...] = (

    ModelCard(
        "claude-opus-4-7", "anthropic", "claude-4", "frontier",
        _caps(reasoning=0.98, coding=0.96, math=0.92, creative=0.94,
              instruction=0.97, long_context=0.96, multimodal_vision=0.92,
              multimodal_audio=0.55, agentic_tool_use=0.97, speed=0.55,
              factuality=0.92, safety_alignment=0.96),
        cost_in_per_mtok=15.0, cost_out_per_mtok=75.0, latency_p50_ms=4200,
        context_window=1_000_000, max_output=32_000,
        modalities=("text", "vision"),
        compliance=("SOC2", "HIPAA", "GDPR", "ISO27001"),
    ),
    ModelCard(
        "claude-sonnet-4-6", "anthropic", "claude-4", "balanced",
        _caps(reasoning=0.94, coding=0.94, math=0.88, creative=0.9,
              instruction=0.95, long_context=0.93, multimodal_vision=0.9,
              multimodal_audio=0.5, agentic_tool_use=0.95, speed=0.78,
              factuality=0.9, safety_alignment=0.95),
        cost_in_per_mtok=3.0, cost_out_per_mtok=15.0, latency_p50_ms=1800,
        context_window=1_000_000, max_output=16_000,
        modalities=("text", "vision"),
        compliance=("SOC2", "HIPAA", "GDPR", "ISO27001"),
    ),
    ModelCard(
        "claude-haiku-4-5", "anthropic", "claude-4", "fast",
        _caps(reasoning=0.82, coding=0.82, math=0.76, creative=0.78,
              instruction=0.9, long_context=0.78, multimodal_vision=0.8,
              multimodal_audio=0.4, agentic_tool_use=0.86, speed=0.96,
              factuality=0.85, safety_alignment=0.94),
        cost_in_per_mtok=0.8, cost_out_per_mtok=4.0, latency_p50_ms=700,
        context_window=200_000, max_output=8_000,
        modalities=("text", "vision"),
        compliance=("SOC2", "HIPAA", "GDPR"),
    ),

    ModelCard(
        "gpt-5", "openai", "gpt-5", "frontier",
        _caps(reasoning=0.97, coding=0.95, math=0.94, creative=0.93,
              instruction=0.96, long_context=0.92, multimodal_vision=0.93,
              multimodal_audio=0.82, agentic_tool_use=0.95, speed=0.55,
              factuality=0.9, safety_alignment=0.93),
        cost_in_per_mtok=10.0, cost_out_per_mtok=40.0, latency_p50_ms=3800,
        context_window=400_000, max_output=32_000,
        modalities=("text", "vision", "audio"),
        compliance=("SOC2", "GDPR", "ISO27001"),
    ),
    ModelCard(
        "gpt-5-mini", "openai", "gpt-5", "fast",
        _caps(reasoning=0.86, coding=0.86, math=0.82, creative=0.82,
              instruction=0.92, long_context=0.82, multimodal_vision=0.86,
              multimodal_audio=0.78, agentic_tool_use=0.9, speed=0.95,
              factuality=0.85, safety_alignment=0.9),
        cost_in_per_mtok=0.6, cost_out_per_mtok=2.4, latency_p50_ms=600,
        context_window=200_000, max_output=16_000,
        modalities=("text", "vision", "audio"),
        compliance=("SOC2", "GDPR"),
    ),
    ModelCard(
        "o4", "openai", "o-series", "specialist",
        _caps(reasoning=0.99, coding=0.93, math=0.98, creative=0.72,
              instruction=0.9, long_context=0.9, multimodal_vision=0.78,
              multimodal_audio=0.4, agentic_tool_use=0.88, speed=0.3,
              factuality=0.92, safety_alignment=0.93),
        cost_in_per_mtok=30.0, cost_out_per_mtok=120.0, latency_p50_ms=12000,
        context_window=400_000, max_output=64_000,
        modalities=("text", "vision"),
        compliance=("SOC2", "GDPR"), notes="Deep reasoning / research",
    ),
    ModelCard(
        "o4-mini", "openai", "o-series", "balanced",
        _caps(reasoning=0.93, coding=0.9, math=0.94, creative=0.7,
              instruction=0.9, long_context=0.88, multimodal_vision=0.72,
              multimodal_audio=0.35, agentic_tool_use=0.86, speed=0.6,
              factuality=0.9, safety_alignment=0.92),
        cost_in_per_mtok=3.0, cost_out_per_mtok=12.0, latency_p50_ms=4500,
        context_window=200_000, max_output=32_000,
        modalities=("text",), compliance=("SOC2", "GDPR"),
    ),

    ModelCard(
        "gemini-2.5-pro", "google", "gemini-2.5", "frontier",
        _caps(reasoning=0.95, coding=0.92, math=0.93, creative=0.9,
              instruction=0.94, long_context=0.99, multimodal_vision=0.96,
              multimodal_audio=0.92, agentic_tool_use=0.92, speed=0.62,
              factuality=0.9, safety_alignment=0.92),
        cost_in_per_mtok=3.5, cost_out_per_mtok=14.0, latency_p50_ms=3000,
        context_window=2_000_000, max_output=64_000,
        modalities=("text", "vision", "audio", "video"),
        compliance=("SOC2", "GDPR", "ISO27001", "HIPAA"),
    ),
    ModelCard(
        "gemini-2.5-flash", "google", "gemini-2.5", "fast",
        _caps(reasoning=0.84, coding=0.82, math=0.82, creative=0.8,
              instruction=0.9, long_context=0.95, multimodal_vision=0.9,
              multimodal_audio=0.88, agentic_tool_use=0.85, speed=0.97,
              factuality=0.85, safety_alignment=0.9),
        cost_in_per_mtok=0.3, cost_out_per_mtok=1.2, latency_p50_ms=550,
        context_window=1_000_000, max_output=32_000,
        modalities=("text", "vision", "audio", "video"),
        compliance=("SOC2", "GDPR"),
    ),

    ModelCard(
        "grok-4", "xai", "grok-4", "frontier",
        _caps(reasoning=0.94, coding=0.91, math=0.9, creative=0.92,
              instruction=0.9, long_context=0.86, multimodal_vision=0.86,
              multimodal_audio=0.55, agentic_tool_use=0.88, speed=0.6,
              factuality=0.84, safety_alignment=0.82),
        cost_in_per_mtok=5.0, cost_out_per_mtok=20.0, latency_p50_ms=2400,
        context_window=256_000, max_output=16_000,
        modalities=("text", "vision"),
        compliance=("SOC2",), notes="Real-time signals via xAI search",
    ),

    ModelCard(
        "llama-4-405b", "meta", "llama-4", "open",
        _caps(reasoning=0.9, coding=0.88, math=0.84, creative=0.86,
              instruction=0.88, long_context=0.88, multimodal_vision=0.84,
              multimodal_audio=0.4, agentic_tool_use=0.82, speed=0.55,
              factuality=0.84, safety_alignment=0.85),
        cost_in_per_mtok=2.0, cost_out_per_mtok=6.0, latency_p50_ms=3200,
        context_window=256_000, max_output=16_000,
        modalities=("text", "vision"),
        compliance=("SOC2", "GDPR"), open_weights=True,
    ),
    ModelCard(
        "llama-4-70b", "meta", "llama-4", "open",
        _caps(reasoning=0.82, coding=0.82, math=0.78, creative=0.8,
              instruction=0.85, long_context=0.82, multimodal_vision=0.78,
              multimodal_audio=0.35, agentic_tool_use=0.78, speed=0.82,
              factuality=0.8, safety_alignment=0.83),
        cost_in_per_mtok=0.35, cost_out_per_mtok=0.9, latency_p50_ms=900,
        context_window=128_000, max_output=8_000,
        modalities=("text", "vision"), open_weights=True,
    ),

    ModelCard(
        "deepseek-r2", "deepseek", "deepseek-r2", "specialist",
        _caps(reasoning=0.95, coding=0.95, math=0.96, creative=0.7,
              instruction=0.86, long_context=0.84, multimodal_vision=0.55,
              multimodal_audio=0.25, agentic_tool_use=0.82, speed=0.45,
              factuality=0.85, safety_alignment=0.78),
        cost_in_per_mtok=0.55, cost_out_per_mtok=2.2, latency_p50_ms=5600,
        context_window=128_000, max_output=32_000,
        modalities=("text",), open_weights=True,
        notes="Strong math / code reasoning at low cost",
    ),
    ModelCard(
        "qwen-3-max", "alibaba", "qwen-3", "frontier",
        _caps(reasoning=0.9, coding=0.9, math=0.9, creative=0.86,
              instruction=0.9, long_context=0.9, multimodal_vision=0.88,
              multimodal_audio=0.7, agentic_tool_use=0.85, speed=0.6,
              factuality=0.85, safety_alignment=0.82),
        cost_in_per_mtok=2.0, cost_out_per_mtok=6.0, latency_p50_ms=2600,
        context_window=256_000, max_output=16_000,
        modalities=("text", "vision", "audio"),
        region_hosted=("cn", "eu"),
    ),
    ModelCard(
        "mistral-large-3", "mistral", "mistral-3", "balanced",
        _caps(reasoning=0.88, coding=0.88, math=0.82, creative=0.86,
              instruction=0.9, long_context=0.82, multimodal_vision=0.74,
              multimodal_audio=0.3, agentic_tool_use=0.84, speed=0.78,
              factuality=0.86, safety_alignment=0.88),
        cost_in_per_mtok=2.5, cost_out_per_mtok=7.5, latency_p50_ms=1400,
        context_window=256_000, max_output=16_000,
        modalities=("text", "vision"),
        compliance=("GDPR", "ISO27001"), region_hosted=("eu",),
    ),
    ModelCard(
        "cohere-command-a", "cohere", "command-a", "balanced",
        _caps(reasoning=0.86, coding=0.82, math=0.78, creative=0.82,
              instruction=0.92, long_context=0.9, multimodal_vision=0.58,
              multimodal_audio=0.25, agentic_tool_use=0.9, speed=0.82,
              factuality=0.92, safety_alignment=0.9),
        cost_in_per_mtok=2.5, cost_out_per_mtok=10.0, latency_p50_ms=1400,
        context_window=256_000, max_output=16_000,
        modalities=("text",), compliance=("SOC2", "GDPR", "ISO27001"),
        notes="Strong RAG / citations",
    ),

    ModelCard(
        "nova-pro", "amazon", "nova", "balanced",
        _caps(reasoning=0.88, coding=0.82, math=0.82, creative=0.84,
              instruction=0.9, long_context=0.86, multimodal_vision=0.88,
              multimodal_audio=0.82, agentic_tool_use=0.86, speed=0.82,
              factuality=0.86, safety_alignment=0.9),
        cost_in_per_mtok=1.0, cost_out_per_mtok=4.0, latency_p50_ms=1400,
        context_window=300_000, max_output=16_000,
        modalities=("text", "vision", "audio", "video"),
        compliance=("SOC2", "HIPAA", "GDPR", "FedRAMP", "ISO27001"),
    ),

    ModelCard(
        "whisper-v4", "openai", "whisper", "specialist",
        _caps(reasoning=0.3, coding=0.2, math=0.2, creative=0.3,
              instruction=0.4, long_context=0.4, multimodal_vision=0.0,
              multimodal_audio=0.98, agentic_tool_use=0.2, speed=0.9,
              factuality=0.92, safety_alignment=0.9),
        cost_in_per_mtok=0.0, cost_out_per_mtok=0.0, latency_p50_ms=1200,
        context_window=8_000, max_output=8_000,
        modalities=("audio",), supports_tools=False,
        notes="Transcription only; priced per audio minute",
    ),
    ModelCard(
        "flux-ultra", "blackforest", "flux", "specialist",
        _caps(reasoning=0.3, coding=0.1, math=0.2, creative=0.98,
              instruction=0.8, long_context=0.2, multimodal_vision=0.98,
              multimodal_audio=0.0, agentic_tool_use=0.1, speed=0.6,
              factuality=0.5, safety_alignment=0.86),
        cost_in_per_mtok=0.0, cost_out_per_mtok=0.0, latency_p50_ms=6000,
        context_window=4_000, max_output=4_000,
        modalities=("vision",), supports_tools=False, supports_streaming=False,
        notes="Text-to-image, priced per image",
    ),
    ModelCard(
        "veo-3", "google", "veo", "specialist",
        _caps(reasoning=0.3, coding=0.1, math=0.2, creative=0.96,
              instruction=0.82, long_context=0.3, multimodal_vision=0.97,
              multimodal_audio=0.6, agentic_tool_use=0.1, speed=0.3,
              factuality=0.55, safety_alignment=0.88),
        cost_in_per_mtok=0.0, cost_out_per_mtok=0.0, latency_p50_ms=120_000,
        context_window=4_000, max_output=4_000,
        modalities=("vision", "audio"),
        supports_tools=False, supports_streaming=False,
        notes="Text-to-video with native audio",
    ),
)


@dataclass(frozen=True)
class AgentCard:
    """An orchestrated runner (multi-step, tool-using)."""
    agent_id: str
    runtime: str
    description: str
    strengths: Tuple[str, ...]
    default_model: str
    fallback_models: Tuple[str, ...]
    supported_tools: Tuple[str, ...]
    max_parallel: int = 1
    autonomy_default: str = "collaborator"
    compliance: Tuple[str, ...] = ()
    cost_overhead_usd: float = 0.0
    notes: str = ""


AGENT_REGISTRY: Tuple[AgentCard, ...] = (
    AgentCard(
        "quick2.research", "quick2-planner",
        "Deep multi-source research agent with citation verification",
        ("prospect", "competitive", "legal research", "market research"),
        default_model="claude-sonnet-4-6",
        fallback_models=("gpt-5", "gemini-2.5-pro"),
        supported_tools=("browser", "serp", "pdf_parser", "vector_search"),
        max_parallel=5, compliance=("SOC2",),
    ),
    AgentCard(
        "quick2.coder", "claude-agent-sdk",
        "Autonomous coding agent: edits, runs tests, iterates",
        ("code fix", "refactor", "test authoring", "PR drafting"),
        default_model="claude-sonnet-4-6",
        fallback_models=("claude-opus-4-7", "gpt-5", "deepseek-r2"),
        supported_tools=("repo_reader", "unit_test_runner", "diff_applier",
                         "static_analysis", "ci_runner"),
        max_parallel=3, compliance=("SOC2",),
    ),
    AgentCard(
        "quick2.analyst", "quick2-planner",
        "Data analyst: SQL, viz, forecasting notebooks",
        ("sql", "analytics", "forecast", "dashboard"),
        default_model="claude-sonnet-4-6",
        fallback_models=("gpt-5", "o4-mini"),
        supported_tools=("python_runner", "bi_api", "chart_export",
                         "etl_tool", "csv_export"),
        max_parallel=2,
    ),
    AgentCard(
        "quick2.creative", "quick2-planner",
        "Creative agent: decks, images, video, storyboards",
        ("image gen", "video gen", "deck", "storyboard"),
        default_model="claude-sonnet-4-6",
        fallback_models=("gemini-2.5-pro",),
        supported_tools=("t2i", "t2v", "ppt_api", "tts", "design_api"),
        max_parallel=3,
    ),
    AgentCard(
        "quick2.ops", "quick2-planner",
        "Operations / RAG agent with long-context comprehension",
        ("RAG", "contracts", "policy scan", "SOP"),
        default_model="gemini-2.5-pro",
        fallback_models=("claude-opus-4-7", "cohere-command-a"),
        supported_tools=("pdf_parser", "vector_search", "table_ocr",
                         "text_scanner"),
        max_parallel=2,
        compliance=("SOC2", "HIPAA", "GDPR"),
    ),
    AgentCard(
        "quick2.sales", "quick2-planner",
        "Sales agent: prospecting, POVs, sequences, CRM updates",
        ("prospect", "proposal", "sequence", "qualify"),
        default_model="claude-sonnet-4-6",
        fallback_models=("gpt-5",),
        supported_tools=("crm_api", "email_api", "marketing_api",
                         "doc_gen", "brand_styles", "browser", "serp"),
        max_parallel=4, autonomy_default="approver",
    ),
    AgentCard(
        "quick2.exec_assistant", "quick2-planner",
        "Executive assistant: email, calendar, tone",
        ("email", "schedule", "tone"),
        default_model="claude-haiku-4-5",
        fallback_models=("gpt-5-mini",),
        supported_tools=("email_api", "calendar_api", "contacts"),
        autonomy_default="approver",
    ),
    AgentCard(
        "quick2.reasoner", "quick2-planner",
        "Deep reasoning agent for hardest problems",
        ("math proof", "architecture design", "policy reasoning"),
        default_model="o4",
        fallback_models=("claude-opus-4-7", "gemini-2.5-pro", "deepseek-r2"),
        supported_tools=(),
    ),
    AgentCard(
        "quick2.safety", "quick2-planner",
        "Safety / compliance guardian; redacts PII, blocks regulated egress",
        ("pii", "compliance", "redaction"),
        default_model="claude-sonnet-4-6",
        fallback_models=("gpt-5",),
        supported_tools=("text_scanner", "audit_store"),
        autonomy_default="approver",
        compliance=("SOC2", "HIPAA", "GDPR", "ISO27001"),
    ),
    AgentCard(
        "quick2.router_self", "quick2-planner",
        "Router self-tuner: replays logs, promotes winning routes",
        ("auto-tune", "bandit exploration", "model promotion"),
        default_model="claude-sonnet-4-6",
        fallback_models=("gpt-5-mini",),
        supported_tools=("router_logs", "tuner", "metrics_store", "feedback_db"),
    ),
)


def models_by_id() -> Dict[str, ModelCard]:
    return {m.model_id: m for m in MODEL_REGISTRY}


def agents_by_id() -> Dict[str, AgentCard]:
    return {a.agent_id: a for a in AGENT_REGISTRY}


def models_by_modality(modality: str) -> List[ModelCard]:
    return [m for m in MODEL_REGISTRY if modality in m.modalities]
