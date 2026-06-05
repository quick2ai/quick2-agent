from __future__ import annotations

import os
import json
from typing import AsyncGenerator
from anthropic import AsyncAnthropic

# Mock responses for dry-run mode when no API key is set
MOCK_FOLLOW_UP = {
    "question": "Can you explain the difference between shared memory and message-passing in multi-agent coordination?",
    "why": "Testing depth on agent communication patterns."
}

MOCK_EVALUATION = {
    "override": False,
    "assessed_level": "B",
    "feedback": "Good understanding demonstrated. Your answer covers the key concepts."
}

MOCK_CURRICULUM_MD = """# 12-Week AI/ML Mastery Curriculum for Levi Webster

## Week 1: Agent Architecture Deep Dive
**Objective:** Master the theoretical foundations of agent loops and cognitive architectures.
- **Resources:**
  - [Software Is Changing (Again) — Andrej Karpathy at YC AI Startup School](https://www.youtube.com/watch?v=LCEmiRjPEtQ) — Karpathy on Software 3.0 and the decade of agents
  - [Cognitive Architectures for Language Agents (CoALA) — Paper Review](https://www.youtube.com/watch?v=jK9jbYOSZvA) — Walkthrough of modular memory, action spaces, and decision-making
  - [LLM Powered Autonomous Agents — Lilian Weng](https://lilianweng.github.io/posts/2023-06-23-agent/) — The canonical overview: Planning, Memory, Tool Use as three pillars
  - [CoALA Paper (arXiv)](https://arxiv.org/abs/2309.02427) — The foundational academic paper
- **Project:** Map ADAM's current architecture against the CoALA framework. Identify which cognitive components (perception, memory, planning, action, reflection) are implemented vs. missing.
- **Success Criteria:** Written architecture comparison document with gap analysis for ADAM.

## Week 2: ReAct & Plan-and-Execute Patterns
**Objective:** Implement and compare ReAct vs. Plan-and-Execute in a real agent.
- **Resources:**
  - [Plan and Execute Agent Design Pattern — Hands-on in LangGraph](https://www.youtube.com/watch?v=vpD9kf5Xwo0) — 24-min hands-on tutorial with theory + implementation
  - [Understanding ReACT with LangChain — Sam Witteveen](https://www.youtube.com/watch?v=Eug2clsLtFs) — Clear walkthrough of the think-act-observe loop
  - [LangGraph: Planning Agents](https://www.youtube.com/watch?v=uRya4zRrRx4) — Three different plan-and-execute agent implementations
  - [ReAct Paper (Yao et al.)](https://arxiv.org/abs/2210.03629) — Original paper on synergizing reasoning and acting
- **Project:** Build a mini-agent for SAM that uses ReAct for simple classification queries and Plan-and-Execute for multi-step CD&E automation tasks.
- **Success Criteria:** Working prototype with benchmarks showing when each pattern wins.

## Week 3: Memory Architectures for Agents
**Objective:** Understand and implement short-term, long-term, and episodic memory for agents.
- **Resources:**
  - [MemGPT — Giving AI Unlimited Prompt Size](https://www.youtube.com/watch?v=QQ2QOPWZKVc) — How MemGPT manages storage tiers for unlimited memory
  - [How to Build AI Agents that Remember with Mem0](https://www.youtube.com/watch?v=m4ZnZXlOOYM) — Practical tutorial on persistent long-term agent memory
  - [AutoGen Agents with Unlimited Memory Using MemGPT](https://www.youtube.com/watch?v=VJ6bK81meu8) — Combining MemGPT with multi-agent systems
- **Project:** Design ADAM's memory architecture — what should be in working memory vs. vector store vs. relational DB for the 900-rep Siemens deployment.
- **Success Criteria:** Memory architecture diagram + prototype memory module for ADAM.

## Week 4: Tool Use & Function Calling
**Objective:** Master tool integration patterns for production agents.
- **Resources:**
  - [LLM Function Calling — AI Tools Deep Dive](https://www.youtube.com/watch?v=gMeTK6zzaO4) — Deep dive into function calling mechanics
  - [Function Calling with ANY LLM (LangChain, HuggingFace, Llama 3)](https://www.youtube.com/watch?v=PPDsrvuPhWQ) — Implement tool use with open-source local LLMs
  - [Anthropic Tool Use Documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview) — Official guide directly applicable to SAM/ADAM
  - [Agentic AI Course — Andrew Ng](https://www.deeplearning.ai/courses/agentic-ai) — Free course covering tool use as an agentic design pattern
- **Project:** Extend SAM's FastAPI wrapper to expose tools that ADAM can call dynamically. Implement tool selection, parameter validation, and error recovery.
- **Success Criteria:** ADAM can dynamically select and call 5+ SAM tools with error handling.

## Week 5: Multi-Agent Orchestration
**Objective:** Deep dive into multi-agent patterns — routing, delegation, consensus.
- **Resources:**
  - [crewAI Crash Course — Multi AI Agent For Complex Use Cases (Krish Naik)](https://www.youtube.com/watch?v=UV81LAb3x2g) — Comprehensive beginner crash course
  - [LangGraph Supervisor Agent Tutorial: Multi-Agent Orchestration](https://www.youtube.com/watch?v=rclPM7dcWMA) — Supervisor pattern for coordinating specialized agents
  - [Multi AI Agent Systems with crewAI — Free Course](https://www.deeplearning.ai/courses/multi-ai-agent-systems-with-crewai) — Structured course on agent collaboration
  - [CrewAI vs LangGraph vs AutoGen — Framework Comparison](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen) — Side-by-side comparison with code examples
- **Project:** Formalize ADAM → SAM/DOM/ACE/ATLAS routing logic. Implement agent handoff protocols with state preservation.
- **Success Criteria:** Documented orchestration protocol + working multi-agent demo.

## Week 6: RAG Advanced Patterns
**Objective:** Move beyond basic RAG — hybrid search, re-ranking, query decomposition.
- **Resources:**
  - [Advanced RAG 06 — RAG Fusion (Sam Witteveen)](https://www.youtube.com/watch?v=GchC5WxeXGc) — Reciprocal rank fusion for better retrieval
  - [Advanced RAG 04 — Contextual Compressors & Filters](https://www.youtube.com/watch?v=4sRigbRITF0) — Advanced post-retrieval processing
  - [Building and Evaluating Advanced RAG Applications — Free Course](https://www.deeplearning.ai/short-courses/building-evaluating-advanced-rag) — Sentence window retrieval + RAG eval triad
  - [Advanced RAG 01 — Self Querying Retrieval](https://www.youtube.com/watch?v=f4LeWlt3T8Y) — LLM-generated structured queries against vector stores
- **Project:** Build a RAG pipeline for JDC Power Systems CD&E documents with hybrid search and re-ranking.
- **Success Criteria:** RAG pipeline with measured retrieval accuracy on JDC test set.

## Week 7: Fine-tuning & Alignment
**Objective:** Understand when and how to fine-tune vs. prompt-engineer vs. RAG.
- **Resources:**
  - [Let's Build the GPT Tokenizer — Andrej Karpathy](https://www.youtube.com/watch?v=zduSFxRajkE) — 2h13m deep-dive building a tokenizer from scratch (BPE, Unicode, regex)
  - [LLM Fine Tuning Explained: LoRA, QLoRA, DPO](https://www.youtube.com/watch?v=wmCmrEijfQ0) — Concise 8-min explainer on fine-tuning methods
  - [The Complete Guide to End-to-End LLM Fine-Tuning](https://www.youtube.com/watch?v=jrf5vyOEMr8) — Full pipeline from data prep to deployment
  - [Fine-tuning LLMs on Human Feedback (RLHF + DPO)](https://www.youtube.com/watch?v=bbVoDXoPrPM) — Comparing RLHF and DPO alignment approaches
- **Project:** Evaluate whether SAM v2.1's macro-F1 0.855 can be improved via fine-tuning Llama 3.1 70B on DGX Spark vs. better prompt engineering.
- **Success Criteria:** Decision matrix + experiment plan for SAM accuracy improvement.

## Week 8: LLM Routing & Cost Optimization
**Objective:** Master hybrid LLM routing for cost/quality optimization.
- **Resources:**
  - [FrugalGPT — How to Use LLMs While Reducing Cost](https://www.youtube.com/watch?v=U3p_f5NWWbU) — Cascade strategy for progressive model routing
  - [Smart LLM Routing — 85% Cheaper With RouteLLM](https://www.youtube.com/watch?v=jc2RCG1Ys7g) — RouteLLM framework for cost-optimized routing
  - [FrugalGPT Paper (Stanford)](https://arxiv.org/abs/2305.05176) — Foundational paper on prompt adaptation and LLM cascade strategies
  - [How LLM Routing Can Save 97% of Your GPT-4 Bill](https://www.youtube.com/watch?v=yMeaNolC8ls) — Practical guide to model selection per task
- **Project:** Formalize Claude Opus (30%) / Llama 3.1 70B (70%) routing rules for ADAM. Build a router that scores query complexity and routes accordingly.
- **Success Criteria:** Working router with measured cost savings vs. quality tradeoffs.

## Week 9: Agent Evaluation & Testing
**Objective:** Learn to systematically evaluate agent performance.
- **Resources:**
  - [Your AI Product Needs Evals — Hamel Husain](https://hamel.dev/blog/posts/evals/) — Authoritative practitioner guide on LLM product evaluation
  - [What We Learned from a Year of Building with LLMs](https://applied-llms.org/) — Landmark guide on evaluation, testing, and ops from shipping practitioners
  - [Task-Specific LLM Evals that Do & Don't Work — Eugene Yan](https://eugeneyan.com/writing/evals/) — Which eval approaches work for which task types
  - [LLM Apps Evaluation Course — Weights & Biases (Free)](https://wandb.ai/site/courses/evals/) — Hands-on course on programmatic checks + LLM judges
- **Project:** Build an evaluation harness for ADAM that tests routing accuracy, end-to-end task completion, and graceful failure handling.
- **Success Criteria:** Evaluation suite with 20+ test cases and automated scoring.

## Week 10: Production Deployment Patterns
**Objective:** Deploy agents reliably at scale.
- **Resources:**
  - [Docker Model Runner on NVIDIA DGX Spark — Build a Local AI App](https://www.youtube.com/watch?v=ANyZCmRktbY) — Run LLMs locally on DGX Spark with Docker, no API keys
  - [NVIDIA DGX Spark Unboxing, Setup and First Impressions](https://www.youtube.com/watch?v=LlXCel4pnHQ) — Hands-on setup including DGX OS, CUDA stack, and AI software
  - [NVIDIA Container Runtime for Docker — DGX Spark User Guide](https://docs.nvidia.com/dgx/dgx-spark/nvidia-container-runtime-for-docker.html) — Official reference for GPU passthrough and container orchestration
- **Project:** Containerize ADAM + SAM stack with Docker Compose for DGX Spark. Implement health checks, logging, and graceful degradation.
- **Success Criteria:** Docker Compose deployment running on DGX Spark with monitoring.

## Week 11: Frontier — Reasoning & Planning
**Objective:** Explore frontier capabilities — chain-of-thought, tree-of-thought, self-reflection.
- **Resources:**
  - [Tree of Thoughts: Deliberate Problem Solving with LLMs — Yannic Kilcher](https://www.youtube.com/watch?v=ut5kp56wW_4) — In-depth walkthrough of Tree-of-Thoughts paper
  - [Reflection Agents — LangChain](https://www.youtube.com/watch?v=v5ymBTXNqtk) — Build three reflection-style agents with self-critique loops
  - [Agentic AI — Reflection Design Pattern (Andrew Ng)](https://learn.deeplearning.ai/courses/agentic-ai/lesson/rm9bg7/agentic-design-patterns) — Andrew Ng teaches iterative self-improvement
  - [Reflexion: Improving AI Agents with Verbal Reinforcement Learning](https://www.youtube.com/watch?v=hNng6ky7fEM) — NeurIPS paper on self-reflective improvement
- **Project:** Implement self-reflection in ADAM — after completing a task, ADAM reviews its own performance and suggests improvements.
- **Success Criteria:** ADAM self-reflection module producing actionable improvement logs.

## Week 12: Capstone — ADAM v2 Architecture
**Objective:** Synthesize everything into a production-grade ADAM v2 design.
- **Resources:**
  - [From Vibe Coding to Agentic Engineering — Andrej Karpathy](https://www.youtube.com/watch?v=96jN2OCOfLs) — Latest Karpathy talk on agentic systems and coordinating agents
  - [The Rise of Agentic Workflows in AI — Andrew Ng](https://www.youtube.com/watch?v=9mylj0ogCFY) — Agentic workflow overview: reflection, tool use, planning, multi-agent
  - [Deep Dive into LLMs like ChatGPT — Andrej Karpathy](https://www.youtube.com/watch?v=7xTGNNLPyMI) — 3.5-hour comprehensive deep dive: pretraining, SFT, RLHF, the full stack
  - [Anthropic Responsible Scaling Policy v3.0](https://www.anthropic.com/news/responsible-scaling-policy-v3) — Production safety framework with deployment gates
- **Project:** Write the ADAM v2 architecture document — memory, routing, tool use, evaluation, deployment. Present to Quick2Labs team / investors.
- **Success Criteria:** Complete architecture document ready for $6M seed deck appendix.
"""


def _get_client() -> AsyncAnthropic | None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        return None
    return AsyncAnthropic(api_key=api_key)


async def generate_follow_up(question_text: str, user_answer: str, domain: str) -> dict:
    """Generate an adaptive follow-up question when user claims mastery."""
    client = _get_client()
    if not client:
        return MOCK_FOLLOW_UP

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""You are an AI/ML assessment expert. The user answered this question:

Question: {question_text}
Domain: {domain}
User's answer: {user_answer}
User self-assessed as: "Could teach it" (highest confidence)

Generate ONE harder follow-up probe question to verify true depth. Return JSON only:
{{"question": "your follow-up question", "why": "brief reason this tests deeper understanding"}}"""
        }]
    )
    try:
        return json.loads(response.content[0].text)
    except (json.JSONDecodeError, IndexError):
        return MOCK_FOLLOW_UP


async def evaluate_free_text(question_text: str, user_answer: str, self_rating: str, domain: str) -> dict:
    """Evaluate a free-text answer and potentially override self-assessment."""
    client = _get_client()
    if not client:
        return MOCK_EVALUATION

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": f"""Evaluate this AI/ML quiz answer. Be fair but rigorous.

Domain: {domain}
Question: {question_text}
Self-assessment: {self_rating}
Answer: {user_answer}

Return JSON only:
{{"override": true/false, "assessed_level": "A/B/C/D", "feedback": "1-2 sentence assessment"}}

Levels: A=Could teach it, B=Solid grasp, C=Rough idea, D=Unknown/wrong"""
        }]
    )
    try:
        return json.loads(response.content[0].text)
    except (json.JSONDecodeError, IndexError):
        return MOCK_EVALUATION


async def generate_curriculum(domain_scores: dict, level: str, strengths: list, gaps: list) -> str:
    """Generate a 12-week personalized curriculum using Claude Opus."""
    from .context import USER_CONTEXT
    from .resources import format_all_resources_for_curriculum

    client = _get_client()
    if not client:
        return MOCK_CURRICULUM_MD

    curated = format_all_resources_for_curriculum()

    response = await client.messages.create(
        model="claude-opus-4-5-20250514",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": f"""Generate a 12-week personalized AI/ML learning curriculum.

{USER_CONTEXT}

Assessment Results:
- Overall Level: {level}
- Domain Scores: {json.dumps(domain_scores, indent=2)}
- Top Strengths: {', '.join(strengths)}
- Top Knowledge Gaps: {', '.join(gaps)}

CURATED RESOURCES — use these real, verified links in the curriculum. Include direct URLs for every resource:
{curated}

Requirements:
1. Each week must include: learning objective, 2-3 resources WITH DIRECT LINKS (YouTube videos, papers, docs, courses), a hands-on project tied to Quick2Labs, and success criteria
2. Use the curated resources above — they are verified, real links. Include the full URL for each resource as a clickable Markdown link.
3. Weight toward knowledge gaps, especially Agentic AI
4. Tie projects directly to: SAM v2.1 FastAPI wrapper, DGX Spark deployment, ADAM multi-agent orchestration, JDC pilot, Siemens 900-rep rollout
5. Each session must be ≤25-30 minutes (ADHD + TBI accommodation)
6. Bottom-line-first, no fluff, high density

Output as clean Markdown with ## headers for each week. Format resources as clickable Markdown links: [Title](URL)"""
        }]
    )
    return response.content[0].text


async def chat_stream(messages: list, week_context: str, week_number: int = 0) -> AsyncGenerator[str, None]:
    """Stream a study-mode chat response."""
    from .context import USER_CONTEXT
    from .resources import format_resources_for_prompt

    client = _get_client()
    if not client:
        mock = "I'm running in mock mode since no API key is configured. Set ANTHROPIC_API_KEY in your .env file to enable live Claude responses. For now, I'd suggest reviewing the week's objectives and trying the hands-on project."
        for word in mock.split():
            yield word + " "
        return

    resources_text = format_resources_for_prompt(week_number) if week_number else ""
    resources_section = f"\n\nRecommended resources for this week (include links when relevant):\n{resources_text}" if resources_text else ""

    system_prompt = f"""{USER_CONTEXT}

You are Levi's AI/ML study tutor. You are currently helping with:
{week_context}{resources_section}

Rules:
- Keep responses concise and actionable (ADHD-friendly)
- Bottom-line first, then details
- Tie concepts back to Levi's real projects (SAM, ADAM, Quick2Labs)
- Use concrete examples, not abstract theory
- When recommending resources, include direct clickable links from the curated list above
- If asked to quiz, generate 3-5 targeted questions on the week's material"""

    async with client.messages.stream(
        model="claude-sonnet-4-5-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def generate_mini_quiz(week_context: str) -> str:
    """Generate a mini-assessment for a specific week."""
    from .context import USER_CONTEXT

    client = _get_client()
    if not client:
        return """## Quick Assessment

1. **What are the three types of memory in an agent architecture?** (Working, Episodic, Semantic)
2. **When would you choose ReAct over Plan-and-Execute?** (Simple, single-step tool calls vs. complex multi-step planning)
3. **How does ADAM's routing pattern classify — single-agent, multi-agent, or hierarchical?** (Hierarchical — ADAM delegates to specialist agents)

*Running in mock mode — set ANTHROPIC_API_KEY for personalized questions.*"""

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""{USER_CONTEXT}

Generate a mini-quiz (3-5 questions) for this week's study material:
{week_context}

Format as Markdown with numbered questions. Include brief expected answers in parentheses after each question. Make questions practical and tied to Levi's projects where possible."""
        }]
    )
    return response.content[0].text
