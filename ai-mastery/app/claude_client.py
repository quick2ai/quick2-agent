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
- **Resources:** "Cognitive Architectures for Language Agents" (CoALA) paper, LangChain agent docs, AutoGPT architecture analysis
- **Project:** Map ADAM's current architecture against the CoALA framework. Identify which cognitive components (perception, memory, planning, action, reflection) are implemented vs. missing.
- **Success Criteria:** Written architecture comparison document with gap analysis for ADAM.

## Week 2: ReAct & Plan-and-Execute Patterns
**Objective:** Implement and compare ReAct vs. Plan-and-Execute in a real agent.
- **Resources:** ReAct paper (Yao et al. 2023), Plan-and-Execute blog (LangChain), Reflexion paper
- **Project:** Build a mini-agent for SAM that uses ReAct for simple classification queries and Plan-and-Execute for multi-step CD&E automation tasks.
- **Success Criteria:** Working prototype with benchmarks showing when each pattern wins.

## Week 3: Memory Architectures for Agents
**Objective:** Understand and implement short-term, long-term, and episodic memory for agents.
- **Resources:** MemGPT paper, Generative Agents paper (Park et al.), Zep memory documentation
- **Project:** Design ADAM's memory architecture — what should be in working memory vs. vector store vs. relational DB for the 900-rep Siemens deployment.
- **Success Criteria:** Memory architecture diagram + prototype memory module for ADAM.

## Week 4: Tool Use & Function Calling
**Objective:** Master tool integration patterns for production agents.
- **Resources:** Anthropic tool use docs, Gorilla paper, ToolBench benchmark
- **Project:** Extend SAM's FastAPI wrapper to expose tools that ADAM can call dynamically. Implement tool selection, parameter validation, and error recovery.
- **Success Criteria:** ADAM can dynamically select and call 5+ SAM tools with error handling.

## Week 5: Multi-Agent Orchestration
**Objective:** Deep dive into multi-agent patterns — routing, delegation, consensus.
- **Resources:** AutoGen paper, CrewAI docs, CAMEL framework analysis
- **Project:** Formalize ADAM → SAM/DOM/ACE/ATLAS routing logic. Implement agent handoff protocols with state preservation.
- **Success Criteria:** Documented orchestration protocol + working multi-agent demo.

## Week 6: RAG Advanced Patterns
**Objective:** Move beyond basic RAG — hybrid search, re-ranking, query decomposition.
- **Resources:** LlamaIndex advanced RAG guide, ColBERT v2 paper, RAPTOR paper
- **Project:** Build a RAG pipeline for JDC Power Systems CD&E documents with hybrid search and re-ranking.
- **Success Criteria:** RAG pipeline with measured retrieval accuracy on JDC test set.

## Week 7: Fine-tuning & Alignment
**Objective:** Understand when and how to fine-tune vs. prompt-engineer vs. RAG.
- **Resources:** QLoRA paper, RLHF overview, DPO paper, Anthropic constitutional AI
- **Project:** Evaluate whether SAM v2.1's macro-F1 0.855 can be improved via fine-tuning Llama 3.1 70B on DGX Spark vs. better prompt engineering.
- **Success Criteria:** Decision matrix + experiment plan for SAM accuracy improvement.

## Week 8: LLM Routing & Cost Optimization
**Objective:** Master hybrid LLM routing for cost/quality optimization.
- **Resources:** FrugalGPT paper, Martian router analysis, semantic router docs
- **Project:** Formalize Claude Opus (30%) / Llama 3.1 70B (70%) routing rules for ADAM. Build a router that scores query complexity and routes accordingly.
- **Success Criteria:** Working router with measured cost savings vs. quality tradeoffs.

## Week 9: Agent Evaluation & Testing
**Objective:** Learn to systematically evaluate agent performance.
- **Resources:** LMSYS Chatbot Arena, AgentBench paper, Inspect AI framework
- **Project:** Build an evaluation harness for ADAM that tests routing accuracy, end-to-end task completion, and graceful failure handling.
- **Success Criteria:** Evaluation suite with 20+ test cases and automated scoring.

## Week 10: Production Deployment Patterns
**Objective:** Deploy agents reliably at scale.
- **Resources:** Anthropic production guide, Modal/Fly.io patterns, DGX Spark deployment docs
- **Project:** Containerize ADAM + SAM stack with Docker Compose for DGX Spark. Implement health checks, logging, and graceful degradation.
- **Success Criteria:** Docker Compose deployment running on DGX Spark with monitoring.

## Week 11: Frontier — Reasoning & Planning
**Objective:** Explore frontier capabilities — chain-of-thought, tree-of-thought, self-reflection.
- **Resources:** Tree of Thoughts paper, Self-Refine paper, Claude extended thinking docs
- **Project:** Implement self-reflection in ADAM — after completing a task, ADAM reviews its own performance and suggests improvements.
- **Success Criteria:** ADAM self-reflection module producing actionable improvement logs.

## Week 12: Capstone — ADAM v2 Architecture
**Objective:** Synthesize everything into a production-grade ADAM v2 design.
- **Resources:** All previous weeks' materials + Anthropic multi-agent best practices
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

    client = _get_client()
    if not client:
        return MOCK_CURRICULUM_MD

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

Requirements:
1. Each week must include: learning objective, 2-3 resources (papers, docs, videos), a hands-on project tied to Quick2Labs, and success criteria
2. Weight toward knowledge gaps, especially Agentic AI
3. Tie projects directly to: SAM v2.1 FastAPI wrapper, DGX Spark deployment, ADAM multi-agent orchestration, JDC pilot, Siemens 900-rep rollout
4. Each session must be ≤25-30 minutes (ADHD + TBI accommodation)
5. Bottom-line-first, no fluff, high density

Output as clean Markdown with ## headers for each week."""
        }]
    )
    return response.content[0].text


async def chat_stream(messages: list, week_context: str) -> AsyncGenerator[str, None]:
    """Stream a study-mode chat response."""
    from .context import USER_CONTEXT

    client = _get_client()
    if not client:
        # Mock streaming for dry-run
        mock = "I'm running in mock mode since no API key is configured. Set ANTHROPIC_API_KEY in your .env file to enable live Claude responses. For now, I'd suggest reviewing the week's objectives and trying the hands-on project."
        for word in mock.split():
            yield word + " "
        return

    system_prompt = f"""{USER_CONTEXT}

You are Levi's AI/ML study tutor. You are currently helping with:
{week_context}

Rules:
- Keep responses concise and actionable (ADHD-friendly)
- Bottom-line first, then details
- Tie concepts back to Levi's real projects (SAM, ADAM, Quick2Labs)
- Use concrete examples, not abstract theory
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
