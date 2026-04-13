# AI/ML Mastery Diagnostic & Curriculum Engine

Personalized AI/ML knowledge diagnostic and 12-week learning curriculum generator for Levi Webster, Quick2Labs.

Built with FastAPI + HTMX + Tailwind + Claude API + SQLite.

## Setup (5 steps)

```bash
# 1. Clone and enter the project
cd ai-mastery

# 2. (Optional) Add your Anthropic API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
# Without a key, the app runs in mock mode with sample responses.

# 3. Run it
chmod +x run.sh
./run.sh

# 4. Open browser
# http://localhost:8000

# 5. Take the diagnostic quiz, generate your curriculum, start studying.
```

That's it. One command: `./run.sh`

## Features

- **Diagnostic Quiz:** 20 questions across 5 domains (ML Foundations, Deep Learning, LLMs/RAG, Agentic AI, Production)
- **Adaptive Follow-ups:** Claim mastery? Claude generates a harder probe to verify
- **Free-text Evaluation:** Optional written answers are evaluated by Claude and can override self-assessment
- **Weighted Scoring:** Agentic AI (35%), LLMs/RAG (25%), Deep Learning (20%), Foundations (10%), Production (10%)
- **Level Placement:** Foundations → Practitioner → Builder → Innovator
- **Knowledge Heatmap:** Bar chart + radar chart of domain scores
- **12-Week Curriculum:** Claude Opus generates a personalized roadmap tied to Quick2Labs projects
- **Study Mode:** Chat with Claude about each week's material, with streaming responses
- **Mini Assessments:** "Quiz me" button for each week generates targeted questions
- **Progress Dashboard:** Score history, level tracking, gap analysis
- **Save & Resume:** Quiz progress persisted to SQLite
- **Downloadable Curriculum:** Export as Markdown

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | HTMX + Tailwind CSS (CDN) |
| LLM | Claude Opus (scoring/curriculum) + Claude Sonnet (chat/evaluation) |
| Database | SQLite + SQLAlchemy (async) |
| Charts | Chart.js (CDN) |

## Project Structure

```
ai-mastery/
├── app/
│   ├── main.py              # FastAPI routes
│   ├── context.py           # User context for Claude prompts
│   ├── models.py            # SQLAlchemy models + DB setup
│   ├── quiz.py              # Question loading + quiz logic
│   ├── scoring.py           # Weighted scoring + level placement
│   ├── curriculum.py        # Curriculum parsing + rendering
│   ├── claude_client.py     # Anthropic SDK wrapper + mock mode
│   └── templates/           # Jinja2 + HTMX templates
├── data/
│   └── questions.yaml       # 20 seed questions (editable)
├── .env.example
├── requirements.txt
├── run.sh                   # One-command launcher
└── README.md
```

## Mock Mode

If `ANTHROPIC_API_KEY` is not set or starts with `sk-ant-your`, the app runs in mock mode:
- Curriculum generation returns a sample 12-week plan
- Follow-up questions return sample probes
- Chat returns a placeholder message
- All quiz scoring and UI features work normally

## Domains & Weights

| Domain | Weight | Questions |
|--------|--------|-----------|
| ML Foundations | 10% | 4 |
| Deep Learning & Transformers | 20% | 4 |
| LLMs, RAG & Fine-tuning | 25% | 4 |
| Agentic AI | 35% | 4 |
| Production & Frontier | 10% | 4 |
