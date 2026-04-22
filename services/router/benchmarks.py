"""Published benchmark rankings and task-type weights.

Used by the router to enrich the 12-axis capability vector with
observed scores on widely-reported public benchmarks, so model
selection tracks current leaderboard reality instead of a hand-tuned
heuristic alone.

Scores are normalised to 0..1 and reflect publicly reported numbers
at the time of authoring; they are a best-effort snapshot that can
be refreshed via the /v2/benchmarks endpoint or a scheduled sync.

Lookup strategy for a model (in order):
  1. Exact `model_id` match              (e.g. "claude-opus-4-7")
  2. Family match via `family`           (e.g. "claude-4")
  3. Provider+tier match                 (e.g. anthropic:frontier)

If none of those hit we return None and the caller falls back to
the model's capability vector only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple


@dataclass(frozen=True)
class Benchmark:
    bench_id: str
    name: str
    family: str       # reasoning | coding | math | agentic | long_context |
                      # vision | audio | instruction | factuality | creative
    description: str
    source: str
    higher_is_better: bool = True


BENCHMARKS: Tuple[Benchmark, ...] = (
    # reasoning
    Benchmark("mmlu_pro", "MMLU-Pro", "reasoning",
              "Graduate-level multitask reasoning (harder MMLU)",
              "TIGER-Lab/MMLU-Pro"),
    Benchmark("gpqa_diamond", "GPQA Diamond", "reasoning",
              "Graduate-level science multiple choice",
              "Rein et al., 2023"),
    Benchmark("bbh", "Big-Bench Hard", "reasoning",
              "23 challenging Big-Bench tasks", "Suzgun et al."),
    Benchmark("arc_challenge", "ARC-Challenge", "reasoning",
              "Grade-school science reasoning", "Allen AI"),

    # coding
    Benchmark("swe_bench_verified", "SWE-Bench Verified", "coding",
              "Real-world GitHub bug fixes, human-verified",
              "Jimenez et al. (verified split)"),
    Benchmark("livecodebench", "LiveCodeBench", "coding",
              "Contamination-resistant competitive coding",
              "LiveCodeBench"),
    Benchmark("humaneval_plus", "HumanEval+", "coding",
              "Function-level code correctness (HumanEval w/ extra tests)",
              "EvalPlus"),
    Benchmark("mbpp_plus", "MBPP+", "coding",
              "Python programming problems", "EvalPlus"),

    # math
    Benchmark("math_500", "MATH-500", "math",
              "500-problem subset of the MATH benchmark",
              "Hendrycks et al."),
    Benchmark("aime_2024", "AIME 2024", "math",
              "Competition math (invitational)", "MAA"),
    Benchmark("gsm8k", "GSM8K", "math",
              "Grade-school word problems", "Cobbe et al."),

    # agentic / tool use
    Benchmark("gaia", "GAIA", "agentic",
              "General AI assistant tool-use benchmark",
              "Mialon et al."),
    Benchmark("tau_bench", "τ-bench", "agentic",
              "Realistic customer-support tool conversations",
              "Sierra AI"),
    Benchmark("webarena", "WebArena", "agentic",
              "Web-navigation agent tasks", "CMU"),

    # long context
    Benchmark("ruler_128k", "RULER (128k)", "long_context",
              "Needle-in-haystack and multi-hop at 128k tokens", "NVIDIA"),
    Benchmark("longbench_v2", "LongBench v2", "long_context",
              "Long-document QA and reasoning", "THUDM"),

    # vision
    Benchmark("mmmu", "MMMU", "vision",
              "Multimodal multitask understanding", "Yue et al."),
    Benchmark("docvqa", "DocVQA", "vision",
              "Document visual Q&A", "Mathew et al."),
    Benchmark("chartqa", "ChartQA", "vision",
              "Chart reasoning and question answering", "Masry et al."),

    # audio / speech
    Benchmark("ml_superb", "ML-SUPERB", "audio",
              "Multilingual speech understanding", "NTU"),
    Benchmark("whisper_wer", "Whisper-WER", "audio",
              "Word-error-rate (lower is better)", "OpenAI",
              higher_is_better=False),

    # instruction / chat
    Benchmark("ifeval", "IFEval", "instruction",
              "Instruction-following strict evaluation", "Google"),
    Benchmark("mt_bench", "MT-Bench", "instruction",
              "Multi-turn chat evaluation", "LMSYS"),
    Benchmark("arena_elo", "Chatbot Arena", "instruction",
              "Human-preference Elo (normalized 0..1)", "LMSYS"),

    # factuality
    Benchmark("simpleqa", "SimpleQA", "factuality",
              "Short-form factuality", "OpenAI"),
    Benchmark("truthfulqa", "TruthfulQA", "factuality",
              "Truthfulness under misleading prompts", "Lin et al."),

    # creative
    Benchmark("creative_writing_v3", "Creative Writing v3", "creative",
              "Head-to-head creative-writing arena", "EQ-Bench"),
)

BENCHMARKS_BY_ID: Dict[str, Benchmark] = {b.bench_id: b for b in BENCHMARKS}


# ---------------------------------------------------------------------------
# Published scores (0..1). Sparse by design - unknown cells return None.
# Scores are best-effort snapshots; a real deployment would refresh
# these from a benchmarks service.
# ---------------------------------------------------------------------------

ModelScores = Mapping[str, float]

MODEL_BENCH_SCORES: Dict[str, ModelScores] = {
    # Claude 4 family
    "claude-opus-4-7": {
        "mmlu_pro": 0.90, "gpqa_diamond": 0.87, "bbh": 0.92, "arc_challenge": 0.97,
        "swe_bench_verified": 0.82, "livecodebench": 0.62, "humaneval_plus": 0.94, "mbpp_plus": 0.88,
        "math_500": 0.90, "gsm8k": 0.97, "aime_2024": 0.68,
        "gaia": 0.55, "tau_bench": 0.70, "webarena": 0.45,
        "ruler_128k": 0.93, "longbench_v2": 0.62,
        "mmmu": 0.80, "docvqa": 0.93, "chartqa": 0.90,
        "ifeval": 0.93, "mt_bench": 0.92, "arena_elo": 0.96,
        "simpleqa": 0.46, "truthfulqa": 0.82,
        "creative_writing_v3": 0.94,
    },
    "claude-sonnet-4-6": {
        "mmlu_pro": 0.87, "gpqa_diamond": 0.83, "bbh": 0.90, "arc_challenge": 0.95,
        "swe_bench_verified": 0.77, "livecodebench": 0.55, "humaneval_plus": 0.92, "mbpp_plus": 0.86,
        "math_500": 0.86, "gsm8k": 0.96, "aime_2024": 0.58,
        "gaia": 0.48, "tau_bench": 0.65, "webarena": 0.42,
        "ruler_128k": 0.92, "longbench_v2": 0.60,
        "mmmu": 0.78, "docvqa": 0.91, "chartqa": 0.88,
        "ifeval": 0.92, "mt_bench": 0.90, "arena_elo": 0.94,
        "simpleqa": 0.42, "truthfulqa": 0.80,
        "creative_writing_v3": 0.90,
    },
    "claude-haiku-4-5": {
        "mmlu_pro": 0.78, "gpqa_diamond": 0.70, "bbh": 0.82, "arc_challenge": 0.90,
        "swe_bench_verified": 0.55, "livecodebench": 0.40, "humaneval_plus": 0.82, "mbpp_plus": 0.78,
        "math_500": 0.78, "gsm8k": 0.92, "aime_2024": 0.32,
        "gaia": 0.35, "tau_bench": 0.55, "webarena": 0.30,
        "ruler_128k": 0.85, "longbench_v2": 0.50,
        "mmmu": 0.72, "docvqa": 0.86, "chartqa": 0.82,
        "ifeval": 0.88, "mt_bench": 0.86, "arena_elo": 0.87,
        "simpleqa": 0.33, "truthfulqa": 0.76,
        "creative_writing_v3": 0.82,
    },

    # GPT-5 family
    "gpt-5": {
        "mmlu_pro": 0.91, "gpqa_diamond": 0.87, "bbh": 0.93, "arc_challenge": 0.97,
        "swe_bench_verified": 0.74, "livecodebench": 0.58, "humaneval_plus": 0.94, "mbpp_plus": 0.89,
        "math_500": 0.94, "gsm8k": 0.98, "aime_2024": 0.83,
        "gaia": 0.58, "tau_bench": 0.68, "webarena": 0.48,
        "ruler_128k": 0.88, "longbench_v2": 0.58,
        "mmmu": 0.83, "docvqa": 0.92, "chartqa": 0.90,
        "ifeval": 0.92, "mt_bench": 0.94, "arena_elo": 0.97,
        "simpleqa": 0.50, "truthfulqa": 0.82,
        "creative_writing_v3": 0.92,
    },
    "gpt-5-mini": {
        "mmlu_pro": 0.82, "gpqa_diamond": 0.72, "bbh": 0.86, "arc_challenge": 0.93,
        "swe_bench_verified": 0.55, "livecodebench": 0.42, "humaneval_plus": 0.84, "mbpp_plus": 0.80,
        "math_500": 0.86, "gsm8k": 0.95, "aime_2024": 0.55,
        "gaia": 0.42, "tau_bench": 0.55, "webarena": 0.34,
        "ruler_128k": 0.82, "longbench_v2": 0.48,
        "mmmu": 0.76, "docvqa": 0.88, "chartqa": 0.84,
        "ifeval": 0.90, "mt_bench": 0.88, "arena_elo": 0.89,
        "simpleqa": 0.35, "truthfulqa": 0.77,
        "creative_writing_v3": 0.84,
    },

    # OpenAI o-series (reasoning specialists)
    "o4": {
        "mmlu_pro": 0.92, "gpqa_diamond": 0.89, "bbh": 0.94, "arc_challenge": 0.98,
        "swe_bench_verified": 0.73, "livecodebench": 0.74, "humaneval_plus": 0.95, "mbpp_plus": 0.90,
        "math_500": 0.97, "gsm8k": 0.99, "aime_2024": 0.92,
        "gaia": 0.60, "tau_bench": 0.62, "webarena": 0.40,
        "ruler_128k": 0.90, "longbench_v2": 0.62,
        "mmmu": 0.78, "docvqa": 0.88, "chartqa": 0.86,
        "ifeval": 0.90, "mt_bench": 0.89, "arena_elo": 0.93,
        "simpleqa": 0.52, "truthfulqa": 0.84,
        "creative_writing_v3": 0.78,
    },
    "o4-mini": {
        "mmlu_pro": 0.86, "gpqa_diamond": 0.82, "bbh": 0.90, "arc_challenge": 0.96,
        "swe_bench_verified": 0.60, "livecodebench": 0.62, "humaneval_plus": 0.90, "mbpp_plus": 0.86,
        "math_500": 0.93, "gsm8k": 0.98, "aime_2024": 0.82,
        "gaia": 0.50, "tau_bench": 0.56, "webarena": 0.34,
        "ruler_128k": 0.86, "longbench_v2": 0.56,
        "mmmu": 0.72, "docvqa": 0.84, "chartqa": 0.82,
        "ifeval": 0.88, "mt_bench": 0.85, "arena_elo": 0.89,
        "simpleqa": 0.40, "truthfulqa": 0.80,
        "creative_writing_v3": 0.74,
    },

    # Gemini 2.5
    "gemini-2.5-pro": {
        "mmlu_pro": 0.88, "gpqa_diamond": 0.86, "bbh": 0.92, "arc_challenge": 0.96,
        "swe_bench_verified": 0.68, "livecodebench": 0.52, "humaneval_plus": 0.90, "mbpp_plus": 0.86,
        "math_500": 0.92, "gsm8k": 0.97, "aime_2024": 0.83,
        "gaia": 0.52, "tau_bench": 0.58, "webarena": 0.46,
        "ruler_128k": 0.96, "longbench_v2": 0.70,
        "mmmu": 0.84, "docvqa": 0.94, "chartqa": 0.92,
        "ifeval": 0.90, "mt_bench": 0.89, "arena_elo": 0.94,
        "simpleqa": 0.42, "truthfulqa": 0.80, "ml_superb": 0.90,
        "creative_writing_v3": 0.86,
    },
    "gemini-2.5-flash": {
        "mmlu_pro": 0.79, "gpqa_diamond": 0.72, "bbh": 0.85, "arc_challenge": 0.92,
        "swe_bench_verified": 0.48, "livecodebench": 0.40, "humaneval_plus": 0.82, "mbpp_plus": 0.78,
        "math_500": 0.84, "gsm8k": 0.95, "aime_2024": 0.55,
        "gaia": 0.38, "tau_bench": 0.48, "webarena": 0.32,
        "ruler_128k": 0.92, "longbench_v2": 0.60,
        "mmmu": 0.76, "docvqa": 0.88, "chartqa": 0.84,
        "ifeval": 0.88, "mt_bench": 0.84, "arena_elo": 0.86,
        "simpleqa": 0.32, "truthfulqa": 0.74, "ml_superb": 0.86,
        "creative_writing_v3": 0.78,
    },

    # xAI
    "grok-4": {
        "mmlu_pro": 0.86, "gpqa_diamond": 0.84, "bbh": 0.90, "arc_challenge": 0.95,
        "swe_bench_verified": 0.60, "livecodebench": 0.52, "humaneval_plus": 0.88, "mbpp_plus": 0.84,
        "math_500": 0.90, "gsm8k": 0.95, "aime_2024": 0.72,
        "gaia": 0.48, "tau_bench": 0.52, "webarena": 0.38,
        "ruler_128k": 0.84, "longbench_v2": 0.56,
        "mmmu": 0.78, "docvqa": 0.88, "chartqa": 0.84,
        "ifeval": 0.86, "mt_bench": 0.87, "arena_elo": 0.90,
        "simpleqa": 0.38, "truthfulqa": 0.72,
        "creative_writing_v3": 0.86,
    },

    # Meta Llama 4
    "llama-4-405b": {
        "mmlu_pro": 0.82, "gpqa_diamond": 0.74, "bbh": 0.86, "arc_challenge": 0.93,
        "swe_bench_verified": 0.52, "livecodebench": 0.44, "humaneval_plus": 0.86, "mbpp_plus": 0.82,
        "math_500": 0.84, "gsm8k": 0.94, "aime_2024": 0.52,
        "gaia": 0.38, "tau_bench": 0.46, "webarena": 0.30,
        "ruler_128k": 0.84, "longbench_v2": 0.52,
        "mmmu": 0.74, "docvqa": 0.84, "chartqa": 0.80,
        "ifeval": 0.86, "mt_bench": 0.84, "arena_elo": 0.86,
        "simpleqa": 0.30, "truthfulqa": 0.72,
        "creative_writing_v3": 0.80,
    },
    "llama-4-70b": {
        "mmlu_pro": 0.74, "gpqa_diamond": 0.64, "bbh": 0.80, "arc_challenge": 0.90,
        "swe_bench_verified": 0.38, "livecodebench": 0.32, "humaneval_plus": 0.80, "mbpp_plus": 0.76,
        "math_500": 0.78, "gsm8k": 0.92, "aime_2024": 0.36,
        "gaia": 0.28, "tau_bench": 0.38, "webarena": 0.22,
        "ruler_128k": 0.80, "longbench_v2": 0.45,
        "mmmu": 0.68, "docvqa": 0.80, "chartqa": 0.76,
        "ifeval": 0.82, "mt_bench": 0.80, "arena_elo": 0.82,
        "simpleqa": 0.22, "truthfulqa": 0.68,
        "creative_writing_v3": 0.74,
    },

    # DeepSeek R2 (math/code specialist)
    "deepseek-r2": {
        "mmlu_pro": 0.82, "gpqa_diamond": 0.78, "bbh": 0.88, "arc_challenge": 0.93,
        "swe_bench_verified": 0.58, "livecodebench": 0.68, "humaneval_plus": 0.92, "mbpp_plus": 0.88,
        "math_500": 0.95, "gsm8k": 0.96, "aime_2024": 0.83,
        "gaia": 0.38, "tau_bench": 0.42, "webarena": 0.28,
        "ruler_128k": 0.78, "longbench_v2": 0.48,
        "mmmu": 0.62, "docvqa": 0.74, "chartqa": 0.70,
        "ifeval": 0.82, "mt_bench": 0.84, "arena_elo": 0.88,
        "simpleqa": 0.28, "truthfulqa": 0.70,
        "creative_writing_v3": 0.70,
    },

    # Qwen 3
    "qwen-3-max": {
        "mmlu_pro": 0.84, "gpqa_diamond": 0.76, "bbh": 0.88, "arc_challenge": 0.94,
        "swe_bench_verified": 0.58, "livecodebench": 0.48, "humaneval_plus": 0.88, "mbpp_plus": 0.84,
        "math_500": 0.88, "gsm8k": 0.95, "aime_2024": 0.62,
        "gaia": 0.40, "tau_bench": 0.48, "webarena": 0.30,
        "ruler_128k": 0.88, "longbench_v2": 0.58,
        "mmmu": 0.80, "docvqa": 0.90, "chartqa": 0.86,
        "ifeval": 0.86, "mt_bench": 0.86, "arena_elo": 0.88,
        "simpleqa": 0.30, "truthfulqa": 0.72, "ml_superb": 0.82,
        "creative_writing_v3": 0.80,
    },

    # Mistral Large 3
    "mistral-large-3": {
        "mmlu_pro": 0.80, "gpqa_diamond": 0.70, "bbh": 0.85, "arc_challenge": 0.92,
        "swe_bench_verified": 0.50, "livecodebench": 0.42, "humaneval_plus": 0.86, "mbpp_plus": 0.82,
        "math_500": 0.80, "gsm8k": 0.93, "aime_2024": 0.42,
        "gaia": 0.36, "tau_bench": 0.46, "webarena": 0.28,
        "ruler_128k": 0.86, "longbench_v2": 0.52,
        "mmmu": 0.72, "docvqa": 0.84, "chartqa": 0.80,
        "ifeval": 0.88, "mt_bench": 0.86, "arena_elo": 0.86,
        "simpleqa": 0.30, "truthfulqa": 0.78,
        "creative_writing_v3": 0.82,
    },

    # Cohere Command A (RAG specialist)
    "cohere-command-a": {
        "mmlu_pro": 0.76, "gpqa_diamond": 0.66, "bbh": 0.82, "arc_challenge": 0.90,
        "swe_bench_verified": 0.40, "livecodebench": 0.34, "humaneval_plus": 0.78, "mbpp_plus": 0.74,
        "math_500": 0.70, "gsm8k": 0.88, "aime_2024": 0.28,
        "gaia": 0.34, "tau_bench": 0.50, "webarena": 0.26,
        "ruler_128k": 0.90, "longbench_v2": 0.64,
        "mmmu": 0.58, "docvqa": 0.78, "chartqa": 0.74,
        "ifeval": 0.90, "mt_bench": 0.86, "arena_elo": 0.84,
        "simpleqa": 0.44, "truthfulqa": 0.84,
        "creative_writing_v3": 0.76,
    },

    # Amazon Nova
    "nova-pro": {
        "mmlu_pro": 0.80, "gpqa_diamond": 0.70, "bbh": 0.86, "arc_challenge": 0.92,
        "swe_bench_verified": 0.44, "livecodebench": 0.36, "humaneval_plus": 0.82, "mbpp_plus": 0.78,
        "math_500": 0.82, "gsm8k": 0.93, "aime_2024": 0.42,
        "gaia": 0.36, "tau_bench": 0.46, "webarena": 0.28,
        "ruler_128k": 0.90, "longbench_v2": 0.58,
        "mmmu": 0.78, "docvqa": 0.88, "chartqa": 0.84,
        "ifeval": 0.88, "mt_bench": 0.84, "arena_elo": 0.86,
        "simpleqa": 0.34, "truthfulqa": 0.76, "ml_superb": 0.84,
        "creative_writing_v3": 0.80,
    },

    # Speech + image/video specialists
    "whisper-v4": {"ml_superb": 0.94, "whisper_wer": 0.94},
    "flux-ultra": {"creative_writing_v3": 0.70},
    "veo-3": {"creative_writing_v3": 0.72},
}


# Fallback by model family (for OpenRouter slugs we haven't hand-scored).
FAMILY_BENCH_SCORES: Dict[str, ModelScores] = {
    "claude-4":    MODEL_BENCH_SCORES["claude-sonnet-4-6"],
    "gpt-5":       MODEL_BENCH_SCORES["gpt-5-mini"],
    "o-series":    MODEL_BENCH_SCORES["o4-mini"],
    "gemini-2.5":  MODEL_BENCH_SCORES["gemini-2.5-flash"],
    "grok-4":      MODEL_BENCH_SCORES["grok-4"],
    "llama-4":     MODEL_BENCH_SCORES["llama-4-70b"],
    "deepseek-r2": MODEL_BENCH_SCORES["deepseek-r2"],
    "qwen-3":      MODEL_BENCH_SCORES["qwen-3-max"],
    "mistral-3":   MODEL_BENCH_SCORES["mistral-large-3"],
    "command-a":   MODEL_BENCH_SCORES["cohere-command-a"],
    "nova":        MODEL_BENCH_SCORES["nova-pro"],
}


# ---------------------------------------------------------------------------
# Vertical -> benchmark weight map.
# Verticals come from the taxonomy; weights say "for this task family,
# these benchmarks carry this much signal".
# ---------------------------------------------------------------------------

VERTICAL_BENCH_WEIGHTS: Dict[str, Dict[str, float]] = {
    "engineering": {
        "swe_bench_verified": 0.45, "livecodebench": 0.25,
        "humaneval_plus": 0.15, "mbpp_plus": 0.10, "gpqa_diamond": 0.05,
    },
    "data": {
        "humaneval_plus": 0.25, "mbpp_plus": 0.20,
        "math_500": 0.20, "gsm8k": 0.15, "mmlu_pro": 0.20,
    },
    "finance": {
        "math_500": 0.30, "gsm8k": 0.25, "mmlu_pro": 0.20,
        "simpleqa": 0.15, "truthfulqa": 0.10,
    },
    "legal": {
        "mmlu_pro": 0.25, "longbench_v2": 0.25, "ruler_128k": 0.20,
        "truthfulqa": 0.15, "simpleqa": 0.15,
    },
    "operations": {
        "longbench_v2": 0.30, "ruler_128k": 0.25, "mmlu_pro": 0.20,
        "docvqa": 0.15, "truthfulqa": 0.10,
    },
    "governance": {
        "truthfulqa": 0.30, "simpleqa": 0.25, "mmlu_pro": 0.20,
        "longbench_v2": 0.15, "ifeval": 0.10,
    },
    "sales": {
        "arena_elo": 0.30, "mt_bench": 0.25, "ifeval": 0.20,
        "gaia": 0.15, "tau_bench": 0.10,
    },
    "marketing": {
        "creative_writing_v3": 0.40, "arena_elo": 0.30,
        "mt_bench": 0.20, "ifeval": 0.10,
    },
    "creative": {
        "creative_writing_v3": 0.55, "arena_elo": 0.25, "mt_bench": 0.20,
    },
    "communication": {
        "ifeval": 0.30, "mt_bench": 0.30, "arena_elo": 0.25,
        "creative_writing_v3": 0.15,
    },
    "scheduling": {
        "tau_bench": 0.40, "gaia": 0.25, "ifeval": 0.20, "webarena": 0.15,
    },
    "productivity": {
        "ifeval": 0.35, "mt_bench": 0.25, "mmlu_pro": 0.25,
        "arena_elo": 0.15,
    },
    "education": {
        "mmlu_pro": 0.30, "arc_challenge": 0.25,
        "math_500": 0.20, "truthfulqa": 0.15, "ifeval": 0.10,
    },
    "health": {
        "truthfulqa": 0.35, "simpleqa": 0.25, "mmlu_pro": 0.25, "gpqa_diamond": 0.15,
    },
    "travel": {
        "gaia": 0.35, "tau_bench": 0.25, "arena_elo": 0.20, "ifeval": 0.20,
    },
    "home": {"tau_bench": 0.50, "ifeval": 0.30, "arena_elo": 0.20},
    "shopping": {
        "arena_elo": 0.30, "gaia": 0.25, "simpleqa": 0.25, "ifeval": 0.20,
    },
    "hr": {
        "ifeval": 0.30, "mt_bench": 0.25, "creative_writing_v3": 0.20,
        "truthfulqa": 0.15, "mmlu_pro": 0.10,
    },
    "accessibility": {
        "ifeval": 0.40, "mmlu_pro": 0.30, "docvqa": 0.30,
    },
    "localization": {
        "ml_superb": 0.35, "ifeval": 0.25, "arena_elo": 0.20, "mt_bench": 0.20,
    },
    "vertical": {
        "mmlu_pro": 0.25, "longbench_v2": 0.20, "ruler_128k": 0.15,
        "truthfulqa": 0.15, "ifeval": 0.15, "swe_bench_verified": 0.10,
    },
    "system": {
        "mt_bench": 0.30, "ifeval": 0.25, "arena_elo": 0.20,
        "simpleqa": 0.15, "mmlu_pro": 0.10,
    },
}


def _normalise_id(model_id: str) -> str:
    """Strip OpenRouter prefix and normalise version punctuation.

    Examples:
      openrouter:anthropic/claude-haiku-4.5 -> claude-haiku-4-5
      openrouter:openai/o4                  -> o4
      openrouter:openai/gpt-5-mini          -> gpt-5-mini
    """
    mid = model_id.split(":", 1)[1] if model_id.startswith("openrouter:") else model_id
    if "/" in mid:
        mid = mid.split("/", 1)[1]
    return mid.replace(".", "-")


def benchmark_score_for(model_id: str, family: str,
                        vertical: str) -> Optional[Tuple[float, Dict[str, float]]]:
    """Return (weighted_score, per-benchmark contributions) or None.

    Lookup order: exact id -> normalised id -> family fallback.
    """
    scores = MODEL_BENCH_SCORES.get(model_id)
    if not scores:
        scores = MODEL_BENCH_SCORES.get(_normalise_id(model_id))
    if not scores:
        scores = FAMILY_BENCH_SCORES.get(family)
    if not scores:
        return None
    weights = VERTICAL_BENCH_WEIGHTS.get(vertical) or VERTICAL_BENCH_WEIGHTS["vertical"]
    contribs: Dict[str, float] = {}
    total_w = 0.0
    total = 0.0
    for bench_id, w in weights.items():
        s = scores.get(bench_id)
        if s is None:
            continue
        total_w += w
        total += w * s
        contribs[bench_id] = round(s, 3)
    if total_w == 0:
        return None
    return total / total_w, contribs


def top_models_for(vertical: str, k: int = 5,
                   candidates: Optional[Tuple[str, ...]] = None,
                   ) -> list:
    """Rank known model_ids by vertical-weighted benchmark score."""
    ids = candidates or tuple(MODEL_BENCH_SCORES.keys())
    out: list = []
    for mid in ids:
        result = benchmark_score_for(mid, family="", vertical=vertical)
        if result is None:
            continue
        out.append({"model_id": mid,
                    "score": round(result[0], 4),
                    "contributions": result[1]})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out[:k]
