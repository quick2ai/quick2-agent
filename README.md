# Quick2 Agent - Python/FastAPI Microservices Monorepo

A production-ready agent orchestration system built with Python 3.11 and FastAPI, featuring 8 interconnected microservices for intelligent task routing, execution, and validation.

## Architecture

### Services

1. **Gateway** (`:8000`) - External API and orchestration
2. **Planner** (`:8001`) - Task decomposition and skill selection
3. **Router** (`:8002`) - Benchmark-based skill routing with Top-1 + alternates
4. **Executor** (`:8003`) - Tool execution with 10 stubbed integrations
5. **Validator** (`:8004`) - Multi-stage validation (JSONSchema, email, pytest, coverage, bias)
6. **Memory** (`:8005`) - User profiles and knowledge base with pgvector
7. **Benchmarks** (`:8006`) - Cron-based leaderboard caching
8. **Dashboard** (`:8007`) - Real-time metrics and analytics UI

### Infrastructure

- **Redis** - Benchmark caching, idempotency keys
- **PostgreSQL + pgvector** - User profiles, knowledge bases, embeddings
- **MinIO** - Artifact storage (S3-compatible)
- **Prometheus** - Metrics collection
- **Grafana** - Visualization dashboards

## Quick Start

### Prerequisites

- Python 3.11
- Docker & Docker Compose
- 8GB+ RAM recommended

### Installation

1. **Clone and setup:**
```bash
cd quick2-agent
cp .env.example .env
```

2. **Install dependencies:**
```bash
pip install -e .[dev]
```

3. **Start all services:**
```bash
docker-compose up --build
```

Services will be available at:
- Gateway API: http://localhost:8000
- Dashboard: http://localhost:8007
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

### Run Tests

```bash
pytest -q
```

## API Examples

### COM-001: Email Composer

Send a professional email with the Email API tool:

```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: com001-$(date +%s)" \
  -d '{
    "task_type": "COM",
    "description": "Draft a professional email to john@example.com about Q4 project updates",
    "context": {
      "to": "john@example.com",
      "subject": "Q4 Project Status Update",
      "tone": "professional"
    },
    "autonomy_mode": "approver"
  }'
```

**Expected Response:**
```json
{
  "task_id": "task-abc123",
  "status": "awaiting_approval",
  "draft_artifact": "minio://drafts/task_abc123_draft.json",
  "provenance": {
    "router_decision": {
      "primary": {"skill_id": "COM-001", "score": 0.92}
    }
  }
}
```

### OPS-001: RAG Query

Perform knowledge base search and generation:

```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: ops001-$(date +%s)" \
  -d '{
    "task_type": "OPS",
    "description": "Find and summarize documentation about API rate limits",
    "context": {
      "query": "API rate limiting best practices",
      "kb_ids": ["kb-001", "kb-002"]
    },
    "autonomy_mode": "collaborator"
  }'
```

**Expected Response:**
```json
{
  "task_id": "task-def456",
  "status": "completed",
  "result": {
    "tool": "vector_search",
    "result": [
      {"id": "doc-1", "score": 0.95, "text": "Relevant passage 1"},
      {"id": "doc-2", "score": 0.89, "text": "Relevant passage 2"}
    ]
  },
  "artifacts": ["minio://artifacts/search_1234.json"],
  "provenance": {
    "latency_ms": 3200,
    "total_cost": 0.05
  }
}
```

### ENG-001: Code Fixer

Analyze and fix code issues with automated testing:

```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: eng001-$(date +%s)" \
  -d '{
    "task_type": "ENG",
    "description": "Fix failing unit tests in the authentication module",
    "context": {
      "repo_url": "https://github.com/example/repo",
      "test_path": "tests/test_auth.py",
      "branch": "main"
    },
    "constraints": {
      "min_coverage": 0.8
    }
  }'
```

**Expected Response:**
```json
{
  "task_id": "task-ghi789",
  "status": "completed",
  "result": {
    "tool": "unit_test_runner",
    "result": "Tests passed: 45/50",
    "metadata": {
      "passed": 45,
      "failed": 5,
      "coverage": 0.87
    }
  },
  "artifacts": ["minio://artifacts/test_results_5678.xml"],
  "provenance": {
    "latency_ms": 7500,
    "total_cost": 0.08,
    "validator_results": [
      {
        "passed": true,
        "checks": {
          "coverage": true,
          "pytest": true
        }
      }
    ]
  }
}
```

## Orchestration Flow

```
User Request → Gateway
    ↓
1. Planner: Classify task → Generate execution steps
    ↓
2. Router: Fetch benchmarks from Redis → Score candidates → Select Top-1 + 2 alternates
    ↓
3. Executor: Run primary skill → Invoke tools (browser, pdf_parser, etc.)
    ↓
4. Validator: JSONSchema + Email rules + Pytest + Coverage + Bias check
    ↓
5. Gateway: Assemble result + Write audit to MinIO → Return to user
```

## Autonomy Engine

The system supports two autonomy modes:

- **Approver**: Requires human approval for external communications (email, calendar)
- **Collaborator**: Full autonomy for internal operations

Skills can override the default mode. See `config/autonomy.yaml` for configuration.

## Tools (Stubbed)

All 10 tools return deterministic mocks with TODOs for real SDK integration:

1. **browser** - Web scraping and interaction
2. **pdf_parser** - PDF text extraction
3. **vector_search** - Semantic search with embeddings
4. **repo_reader** - Git repository analysis
5. **unit_test_runner** - Pytest execution and coverage
6. **email_api** - Email composition and sending
7. **calendar_api** - Calendar event management
8. **ppt_api** - PowerPoint generation
9. **tts** - Text-to-speech synthesis
10. **asr** - Automatic speech recognition

## Development

### Linting & Type Checking

```bash
ruff check .
mypy services/
```

### Running Individual Services

```bash
python services/gateway/main.py
python services/planner/main.py
```

### Environment Variables

See `.env.example` for all configuration options.

## Telemetry

OpenTelemetry instrumentation is enabled on all services. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to send traces to your observability platform.

## Dashboard

Visit http://localhost:8007 to view:
- Task stream (last 20 tasks)
- Success rate, P50/P95 latency
- Cost per task, fallback rates
- Per-skill ROI analysis

## Production Deployment

1. Update `.env` with production credentials
2. Set `SESSION_SECRET` to a secure random value
3. Configure `OTEL_EXPORTER_OTLP_ENDPOINT` for tracing
4. Review `config/autonomy.yaml` for approval requirements
5. Deploy with `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up`

## License

MIT
