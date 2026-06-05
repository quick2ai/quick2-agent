from __future__ import annotations

CURATED_RESOURCES: dict[int, dict] = {
    1: {
        "title": "Agent Architecture Deep Dive",
        "resources": [
            {
                "title": "Software Is Changing (Again) — Andrej Karpathy at YC AI Startup School",
                "url": "https://www.youtube.com/watch?v=LCEmiRjPEtQ",
                "type": "video",
                "creator": "Andrej Karpathy",
                "description": "Karpathy introduces Software 3.0 and the decade of agents — what agent architecture means at a high level.",
            },
            {
                "title": "Cognitive Architectures for Language Agents (CoALA) — Paper Review",
                "url": "https://www.youtube.com/watch?v=jK9jbYOSZvA",
                "type": "video",
                "creator": "Paper Review Channel",
                "description": "Walkthrough of the CoALA paper covering modular memory components, structured action spaces, and decision-making.",
            },
            {
                "title": "LLM Powered Autonomous Agents — Lilian Weng",
                "url": "https://lilianweng.github.io/posts/2023-06-23-agent/",
                "type": "blog",
                "creator": "Lilian Weng (OpenAI)",
                "description": "The most-referenced overview of LLM agent architecture: Planning, Memory, and Tool Use as three pillars.",
            },
            {
                "title": "CoALA Paper (arXiv)",
                "url": "https://arxiv.org/abs/2309.02427",
                "type": "paper",
                "creator": "Sumers et al.",
                "description": "The foundational paper unifying agent architecture into memory, action, and decision-making modules.",
            },
        ],
    },
    2: {
        "title": "ReAct & Plan-and-Execute Patterns",
        "resources": [
            {
                "title": "Plan and Execute Agent Design Pattern — Hands-on in LangGraph",
                "url": "https://www.youtube.com/watch?v=vpD9kf5Xwo0",
                "type": "video",
                "creator": "AI Bites",
                "description": "24-minute hands-on tutorial covering theory and implementation of Plan-and-Execute using LangGraph.",
            },
            {
                "title": "Understanding ReACT with LangChain — Sam Witteveen",
                "url": "https://www.youtube.com/watch?v=Eug2clsLtFs",
                "type": "video",
                "creator": "Sam Witteveen",
                "description": "Clear walkthrough of the ReAct (Reasoning + Acting) pattern covering the think-act-observe loop.",
            },
            {
                "title": "LangGraph: Planning Agents",
                "url": "https://www.youtube.com/watch?v=uRya4zRrRx4",
                "type": "video",
                "creator": "LangChain",
                "description": "How to build three different plan-and-execute style agents using LangGraph.",
            },
            {
                "title": "ReAct: Synergizing Reasoning and Acting in Language Models (Original Paper)",
                "url": "https://arxiv.org/abs/2210.03629",
                "type": "paper",
                "creator": "Yao et al.",
                "description": "The original ReAct paper — essential reading on combining reasoning traces with action generation.",
            },
        ],
    },
    3: {
        "title": "Memory Architectures for Agents",
        "resources": [
            {
                "title": "MemGPT — Giving AI Unlimited Prompt Size",
                "url": "https://www.youtube.com/watch?v=QQ2QOPWZKVc",
                "type": "video",
                "creator": "AI Channel",
                "description": "Overview of MemGPT's approach to unlimited memory via intelligent storage tier management.",
            },
            {
                "title": "How to Build AI Agents that Remember with Mem0",
                "url": "https://www.youtube.com/watch?v=m4ZnZXlOOYM",
                "type": "video",
                "creator": "AI Tutorial",
                "description": "Practical tutorial on giving agents persistent long-term memory using the Mem0 framework.",
            },
            {
                "title": "AutoGen Agents with Unlimited Memory Using MemGPT",
                "url": "https://www.youtube.com/watch?v=VJ6bK81meu8",
                "type": "video",
                "creator": "AI Tutorial",
                "description": "Hands-on: combining MemGPT with AutoGen agents for unlimited memory in multi-agent systems.",
            },
            {
                "title": "LLM Powered Autonomous Agents — Memory Section (Lilian Weng)",
                "url": "https://lilianweng.github.io/posts/2023-06-23-agent/",
                "type": "blog",
                "creator": "Lilian Weng",
                "description": "Canonical taxonomy of short-term vs. long-term memory used by most agent frameworks.",
            },
        ],
    },
    4: {
        "title": "Tool Use & Function Calling",
        "resources": [
            {
                "title": "LLM Function Calling — AI Tools Deep Dive",
                "url": "https://www.youtube.com/watch?v=gMeTK6zzaO4",
                "type": "video",
                "creator": "AI Engineering",
                "description": "Deep dive into tool and function calling mechanics that power AI agents.",
            },
            {
                "title": "Function Calling with ANY LLM (LangChain, HuggingFace, Llama 3)",
                "url": "https://www.youtube.com/watch?v=PPDsrvuPhWQ",
                "type": "video",
                "creator": "AI Tutorial",
                "description": "Implement function calling with open-source local LLMs, not just proprietary APIs.",
            },
            {
                "title": "Anthropic Tool Use Documentation",
                "url": "https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview",
                "type": "docs",
                "creator": "Anthropic",
                "description": "Official Anthropic guide to tool use with Claude — directly applicable to SAM/ADAM integration.",
            },
            {
                "title": "Agentic AI Course — Tool Use Pattern (Andrew Ng)",
                "url": "https://www.deeplearning.ai/courses/agentic-ai",
                "type": "course",
                "creator": "DeepLearning.AI",
                "description": "Free course covering four agentic design patterns including tool use, with hands-on Python.",
            },
        ],
    },
    5: {
        "title": "Multi-Agent Orchestration",
        "resources": [
            {
                "title": "crewAI Crash Course — Multi AI Agent For Complex Use Cases",
                "url": "https://www.youtube.com/watch?v=UV81LAb3x2g",
                "type": "video",
                "creator": "Krish Naik",
                "description": "Comprehensive beginner crash course on CrewAI for multi-agent systems.",
            },
            {
                "title": "LangGraph Supervisor Agent Tutorial: Master Multi-Agent Orchestration",
                "url": "https://www.youtube.com/watch?v=rclPM7dcWMA",
                "type": "video",
                "creator": "AI Tutorial",
                "description": "Hands-on supervisor pattern for coordinating multiple specialized agents — maps to ADAM architecture.",
            },
            {
                "title": "Multi AI Agent Systems with crewAI (Free Course)",
                "url": "https://www.deeplearning.ai/courses/multi-ai-agent-systems-with-crewai",
                "type": "course",
                "creator": "DeepLearning.AI",
                "description": "Structured course on multi-agent systems covering task decomposition and agent collaboration.",
            },
            {
                "title": "CrewAI vs LangGraph vs AutoGen — Framework Comparison",
                "url": "https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen",
                "type": "blog",
                "creator": "DataCamp",
                "description": "Side-by-side comparison with code examples to help choose the right orchestration framework.",
            },
        ],
    },
    6: {
        "title": "RAG Advanced Patterns",
        "resources": [
            {
                "title": "Advanced RAG 06 — RAG Fusion (Sam Witteveen)",
                "url": "https://www.youtube.com/watch?v=GchC5WxeXGc",
                "type": "video",
                "creator": "Sam Witteveen",
                "description": "RAG Fusion using reciprocal rank fusion to combine multiple search queries for better retrieval.",
            },
            {
                "title": "Advanced RAG 04 — Contextual Compressors & Filters",
                "url": "https://www.youtube.com/watch?v=4sRigbRITF0",
                "type": "video",
                "creator": "Sam Witteveen",
                "description": "Advanced post-retrieval processing with LLM extractors and chain filters.",
            },
            {
                "title": "Building and Evaluating Advanced RAG Applications (Free Course)",
                "url": "https://www.deeplearning.ai/short-courses/building-evaluating-advanced-rag",
                "type": "course",
                "creator": "DeepLearning.AI",
                "description": "Sentence window retrieval, auto-merging retrieval, and RAG evaluation triad.",
            },
            {
                "title": "Advanced RAG 01 — Self Querying Retrieval",
                "url": "https://www.youtube.com/watch?v=f4LeWlt3T8Y",
                "type": "video",
                "creator": "Sam Witteveen",
                "description": "Self-querying retrieval where the LLM generates structured queries against the vector store.",
            },
        ],
    },
    7: {
        "title": "Fine-tuning & Alignment",
        "resources": [
            {
                "title": "Let's Build the GPT Tokenizer — Andrej Karpathy",
                "url": "https://www.youtube.com/watch?v=zduSFxRajkE",
                "type": "video",
                "creator": "Andrej Karpathy",
                "description": "2h13m deep-dive building a GPT tokenizer from scratch — BPE, Unicode, regex patterns. Definitive resource.",
            },
            {
                "title": "LLM Fine Tuning Explained: LoRA, QLoRA, DPO",
                "url": "https://www.youtube.com/watch?v=wmCmrEijfQ0",
                "type": "video",
                "creator": "AI Engineering",
                "description": "Concise 8-minute explainer covering full fine-tuning vs. PEFT methods plus alignment techniques.",
            },
            {
                "title": "The Complete Guide to End-to-End LLM Fine-Tuning",
                "url": "https://www.youtube.com/watch?v=jrf5vyOEMr8",
                "type": "video",
                "creator": "AI Engineering",
                "description": "Full pipeline from data prep to deployment for fine-tuning large language models.",
            },
            {
                "title": "Fine-tuning LLMs on Human Feedback (RLHF + DPO)",
                "url": "https://www.youtube.com/watch?v=bbVoDXoPrPM",
                "type": "video",
                "creator": "AI Engineering",
                "description": "Focused tutorial comparing RLHF and DPO alignment approaches.",
            },
        ],
    },
    8: {
        "title": "LLM Routing & Cost Optimization",
        "resources": [
            {
                "title": "FrugalGPT — How to Use LLMs While Reducing Cost",
                "url": "https://www.youtube.com/watch?v=U3p_f5NWWbU",
                "type": "video",
                "creator": "AI Channel",
                "description": "FrugalGPT's cascade strategy for routing queries to progressively more capable models based on confidence.",
            },
            {
                "title": "Smart LLM Routing — 85% Cheaper With RouteLLM",
                "url": "https://www.youtube.com/watch?v=jc2RCG1Ys7g",
                "type": "video",
                "creator": "AI Tutorial",
                "description": "RouteLLM framework achieving 85% cost reduction while maintaining 95% of GPT-4 performance.",
            },
            {
                "title": "FrugalGPT Paper (Stanford)",
                "url": "https://arxiv.org/abs/2305.05176",
                "type": "paper",
                "creator": "Chen, Zaharia, Zou (Stanford)",
                "description": "Foundational paper on prompt adaptation, LLM approximation, and cascade strategies for 98% cost reduction.",
            },
            {
                "title": "How LLM Routing Can Save 97% of Your GPT-4 Bill",
                "url": "https://www.youtube.com/watch?v=yMeaNolC8ls",
                "type": "video",
                "creator": "AI Channel",
                "description": "Practical guide to choosing the right model per task for optimal cost/performance.",
            },
        ],
    },
    9: {
        "title": "Agent Evaluation & Testing",
        "resources": [
            {
                "title": "Your AI Product Needs Evals — Hamel Husain",
                "url": "https://hamel.dev/blog/posts/evals/",
                "type": "blog",
                "creator": "Hamel Husain",
                "description": "Authoritative practitioner guide on building evaluation systems for LLM-powered products.",
            },
            {
                "title": "What We Learned from a Year of Building with LLMs",
                "url": "https://applied-llms.org/",
                "type": "blog",
                "creator": "Eugene Yan, Hamel Husain, et al.",
                "description": "Landmark guide covering evaluation, testing, monitoring, and ops from practitioners who ship LLM products.",
            },
            {
                "title": "Task-Specific LLM Evals that Do & Don't Work",
                "url": "https://eugeneyan.com/writing/evals/",
                "type": "blog",
                "creator": "Eugene Yan",
                "description": "Practical breakdown of which evaluation approaches work for different task types in production.",
            },
            {
                "title": "LLM Apps Evaluation Course (Free)",
                "url": "https://wandb.ai/site/courses/evals/",
                "type": "course",
                "creator": "Weights & Biases",
                "description": "Hands-on course on building evaluation pipelines combining programmatic checks with LLM judges.",
            },
        ],
    },
    10: {
        "title": "Production Deployment Patterns",
        "resources": [
            {
                "title": "Docker Model Runner on NVIDIA DGX Spark — Build a Local AI App",
                "url": "https://www.youtube.com/watch?v=ANyZCmRktbY",
                "type": "video",
                "creator": "Docker (Official)",
                "description": "Run LLMs locally on DGX Spark with GPU acceleration using Docker Model Runner — no API keys needed.",
            },
            {
                "title": "NVIDIA DGX Spark Unboxing, Setup and First Impressions",
                "url": "https://www.youtube.com/watch?v=LlXCel4pnHQ",
                "type": "video",
                "creator": "Tech Review",
                "description": "Hands-on setup of DGX Spark including NVIDIA DGX OS, drivers, CUDA stack, and AI software environment.",
            },
            {
                "title": "NVIDIA Container Runtime for Docker — DGX Spark User Guide",
                "url": "https://docs.nvidia.com/dgx/dgx-spark/nvidia-container-runtime-for-docker.html",
                "type": "docs",
                "creator": "NVIDIA (Official)",
                "description": "Official reference for GPU passthrough, memory management, volume mounting, and container orchestration.",
            },
        ],
    },
    11: {
        "title": "Frontier — Reasoning & Planning",
        "resources": [
            {
                "title": "Tree of Thoughts: Deliberate Problem Solving with LLMs — Yannic Kilcher",
                "url": "https://www.youtube.com/watch?v=ut5kp56wW_4",
                "type": "video",
                "creator": "Yannic Kilcher",
                "description": "In-depth paper walkthrough of Tree-of-Thoughts — generalizing chain-of-thought via tree search.",
            },
            {
                "title": "Reflection Agents — LangChain",
                "url": "https://www.youtube.com/watch?v=v5ymBTXNqtk",
                "type": "video",
                "creator": "LangChain",
                "description": "Build three reflection-style agents using LangGraph — practical self-critique and self-correction loops.",
            },
            {
                "title": "Agentic AI — Reflection Design Pattern (Andrew Ng)",
                "url": "https://learn.deeplearning.ai/courses/agentic-ai/lesson/rm9bg7/agentic-design-patterns",
                "type": "course",
                "creator": "DeepLearning.AI",
                "description": "Andrew Ng teaches the Reflection pattern where agents examine and iteratively improve their own output.",
            },
            {
                "title": "Reflexion: Improving AI Agents with Verbal Reinforcement Learning",
                "url": "https://www.youtube.com/watch?v=hNng6ky7fEM",
                "type": "video",
                "creator": "Paper Walkthrough",
                "description": "NeurIPS paper walkthrough on agents converting environment feedback into self-reflective improvement.",
            },
        ],
    },
    12: {
        "title": "Capstone — ADAM v2 Architecture",
        "resources": [
            {
                "title": "From Vibe Coding to Agentic Engineering — Andrej Karpathy",
                "url": "https://www.youtube.com/watch?v=96jN2OCOfLs",
                "type": "video",
                "creator": "Andrej Karpathy",
                "description": "Latest Karpathy talk on agentic systems, software paradigm evolution, and coordinating agents.",
            },
            {
                "title": "The Rise of Agentic Workflows in AI — Andrew Ng",
                "url": "https://www.youtube.com/watch?v=9mylj0ogCFY",
                "type": "video",
                "creator": "Andrew Ng",
                "description": "Overview of agentic workflows covering reflection, tool use, planning, and multi-agent collaboration.",
            },
            {
                "title": "Deep Dive into LLMs like ChatGPT — Andrej Karpathy",
                "url": "https://www.youtube.com/watch?v=7xTGNNLPyMI",
                "type": "video",
                "creator": "Andrej Karpathy",
                "description": "3.5-hour comprehensive deep dive covering pretraining, SFT, RLHF, tokenization — the full LLM stack.",
            },
            {
                "title": "Anthropic Responsible Scaling Policy v3.0",
                "url": "https://www.anthropic.com/news/responsible-scaling-policy-v3",
                "type": "docs",
                "creator": "Anthropic",
                "description": "Production-level safety framework with AI Safety Levels and deployment gates — applicable to ADAM.",
            },
        ],
    },
}

# Bonus foundational resources referenced across multiple weeks
FOUNDATIONAL_RESOURCES = [
    {
        "title": "Let's build GPT: from scratch, in code — Andrej Karpathy",
        "url": "https://www.youtube.com/watch?v=kCc8FmEb1nY",
        "type": "video",
        "creator": "Andrej Karpathy",
        "description": "Builds a GPT from scratch covering self-attention, multi-head attention, and the full transformer decoder.",
    },
    {
        "title": "But what is a GPT? Visual intro to transformers — 3Blue1Brown",
        "url": "https://www.youtube.com/watch?v=wjZofJX0v4M",
        "type": "video",
        "creator": "3Blue1Brown",
        "description": "Visual introduction to how transformers and large language models work.",
    },
    {
        "title": "Attention in transformers, visually explained — 3Blue1Brown",
        "url": "https://www.youtube.com/watch?v=eMlx5fFNoYc",
        "type": "video",
        "creator": "3Blue1Brown",
        "description": "Deep visual dive into keys, queries, values — the attention mechanism inside transformers.",
    },
    {
        "title": "The spelled-out intro to neural networks and backpropagation — Andrej Karpathy",
        "url": "https://www.youtube.com/watch?v=VMj-3S1tku0",
        "type": "video",
        "creator": "Andrej Karpathy",
        "description": "From-scratch backpropagation by building an autograd engine. The best backprop tutorial on YouTube.",
    },
    {
        "title": "StatQuest: Bias and Variance",
        "url": "https://www.youtube.com/watch?v=EuBBz3bI-aA",
        "type": "video",
        "creator": "StatQuest (Josh Starmer)",
        "description": "Clear visual explanation of bias-variance tradeoff.",
    },
    {
        "title": "StatQuest: Gradient Descent, Step-by-Step",
        "url": "https://www.youtube.com/watch?v=sDv4f4s2SB8",
        "type": "video",
        "creator": "StatQuest (Josh Starmer)",
        "description": "Step-by-step walkthrough of gradient descent.",
    },
    {
        "title": "AI Prompt Engineering: A Deep Dive — Anthropic",
        "url": "https://www.youtube.com/watch?v=T9aRN5JkmL8",
        "type": "video",
        "creator": "Anthropic",
        "description": "Anthropic experts on chain-of-thought, XML tagging, system prompting, and Claude-specific best practices.",
    },
    {
        "title": "Anthropic Interactive Prompt Engineering Tutorial",
        "url": "https://github.com/anthropics/prompt-eng-interactive-tutorial",
        "type": "course",
        "creator": "Anthropic",
        "description": "9-chapter hands-on course with exercises on prompting techniques.",
    },
    {
        "title": "Intro to AI Safety, Remastered — Robert Miles",
        "url": "https://www.youtube.com/watch?v=pYXy-A4siMw",
        "type": "video",
        "creator": "Robert Miles",
        "description": "Comprehensive introduction to AI safety: alignment, reward hacking, specification gaming.",
    },
]


def get_resources_for_week(week: int) -> list[dict]:
    """Get curated resources for a specific curriculum week."""
    week_data = CURATED_RESOURCES.get(week)
    if not week_data:
        return []
    return week_data["resources"]


def format_resources_for_prompt(week: int) -> str:
    """Format resources as text for injection into Claude prompts."""
    resources = get_resources_for_week(week)
    if not resources:
        return ""

    lines = []
    for r in resources:
        icon = {"video": "🎥", "blog": "📝", "paper": "📄", "docs": "📚", "course": "🎓"}.get(r["type"], "📎")
        lines.append(f"- {icon} [{r['title']}]({r['url']}) — {r['creator']}: {r['description']}")
    return "\n".join(lines)


def format_all_resources_for_curriculum() -> str:
    """Format all curated resources for the curriculum generation prompt."""
    sections = []
    for week_num, week_data in CURATED_RESOURCES.items():
        section = f"\n### Week {week_num}: {week_data['title']}"
        for r in week_data["resources"]:
            section += f"\n- [{r['title']}]({r['url']}) ({r['type']}) — {r['creator']}"
        sections.append(section)
    return "\n".join(sections)
