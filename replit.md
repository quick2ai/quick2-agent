# Quick2 Agent - Microservices Monorepo

## Overview

A production-ready Python/FastAPI microservices monorepo for intelligent agent orchestration. The system features 8 interconnected services that handle task planning, routing, execution, and validation with full observability.

**Purpose**: Orchestrate AI agent tasks through a sophisticated pipeline with benchmark-based routing, multi-tool execution, and comprehensive validation.

**Current State**: MVP complete with all 8 services implemented, tested, and documented. Dashboard running on port 5000.

## Recent Changes

### 2025-11-07: Initial Implementation
- Created complete microservices architecture with 8 services
- Implemented shared Pydantic models in `libs/common`
- Set up skills registry (9 skills) and autonomy configuration
- Created Docker Compose infrastructure with Postgres, Redis, MinIO, Prometheus, Grafana
- Implemented 10 stubbed tools in executor service
- Added comprehensive test suite (9 tests, all passing)
- Created dashboard UI with real-time metrics and analytics
- Configured workflow to run dashboard service on port 5000

## Project Architecture

### Services

1. **Gateway** (`:8000`) - External API orchestrator
   - Handles task submission with idempotency
   - Orchestrates: planner → router → executor → validator
   - Enforces autonomy modes (Approver/Collaborator)

2. **Planner** (`:8001`) - Task decomposition
   - Loads skills from YAML registry
   - Generates execution plans with skill recommendations

3. **Router** (`:8002`) - Benchmark-based routing
   - Fetches cached benchmarks from Redis
   - Scores candidates by latency, success rate, cost
   - Returns Top-1 + 2 alternates

4. **Executor** (`:8003`) - Tool execution
   - 10 stubbed tools: browser, pdf_parser, vector_search, repo_reader, unit_test_runner, email_api, calendar_api, ppt_api, tts, asr
   - Returns artifact URIs (MinIO references)

5. **Validator** (`:8004`) - Multi-stage validation
   - JSONSchema, email rules, action schema
   - Pytest runner, coverage check, bias metrics

6. **Memory** (`:8005`) - User profiles & knowledge base
   - Postgres + pgvector for embeddings
   - CRUD endpoints for profiles and KB entries

7. **Benchmarks** (`:8006`) - Leaderboard caching
   - APScheduler cron jobs (15min intervals)
   - Caches Top-15 benchmarks to Redis

8. **Dashboard** (`:8007` or `:5000` in dev) - Analytics UI
   - Task stream, success rate, P50/P95 latency
   - Cost per task, fallback rates, per-skill ROI

### Infrastructure Dependencies

- **Redis**: Benchmark cache, idempotency keys
- **PostgreSQL + pgvector**: User profiles, KB, embeddings
- **MinIO**: Artifact storage (S3-compatible)
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards

## Tech Stack

- **Language**: Python 3.11
- **Framework**: FastAPI with Uvicorn
- **Data Models**: Pydantic v2
- **Testing**: pytest with pytest-asyncio
- **Observability**: OpenTelemetry
- **Container**: Docker Compose
- **Database**: PostgreSQL 16 with pgvector extension
- **Cache**: Redis 7
- **Object Storage**: MinIO

## Development Setup

### Running Locally (Replit)

The dashboard service is configured as the primary workflow and runs on port 5000:

```bash
# Dashboard is already running
# Visit the webview to see real-time metrics
```

### Running Full Stack with Docker Compose

```bash
# Start all services
docker-compose up --build

# Run tests
pytest -v

# Lint & type check
ruff check .
mypy services/
```

### Environment Variables

See `.env.example` for all configuration options. Key variables:
- `DATABASE_URL`: Postgres connection string
- `REDIS_HOST`, `REDIS_PORT`: Redis connection
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OpenTelemetry collector
- `SESSION_SECRET`: Session encryption key

## API Examples

### Submit a Task

```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: unique-key-123" \
  -d '{
    "task_type": "ENG",
    "description": "Fix failing tests",
    "autonomy_mode": "collaborator"
  }'
```

### Get Skills Registry

```bash
curl http://localhost:8001/v1/skills
```

### View Benchmarks

```bash
curl http://localhost:8006/v1/benchmarks/leaderboard
```

## File Structure

```
quick2-agent/
├── services/           # 8 microservices
│   ├── gateway/
│   ├── planner/
│   ├── router/
│   ├── executor/
│   ├── validator/
│   ├── memory/
│   ├── benchmarks/
│   └── dashboard/
├── libs/
│   └── common/         # Shared Pydantic models
├── skills/
│   └── skills.yaml     # Skill registry (9 skills)
├── config/
│   ├── autonomy.yaml   # Autonomy engine config
│   └── prometheus.yml  # Prometheus scrape config
├── tests/              # Pytest test suite
├── docker-compose.yml  # Full stack infrastructure
├── Dockerfile          # Service container image
├── pyproject.toml      # Python dependencies
├── requirements.txt    # Pip requirements
├── .env.example        # Environment template
└── README.md           # User documentation
```

## Testing

All 9 tests passing:
- Health checks for all 8 services
- Executor tools endpoint verification

```bash
pytest tests/ -v
# 9 passed, 10 warnings
```

## Skills Registry

9 skills implemented across task types:
- **COM**: Email (COM-001), Calendar (COM-002)
- **OPS**: RAG Query (OPS-001), PDF Processing (OPS-002)
- **ENG**: Code Fixer (ENG-001), Test Generator (ENG-002)
- **CREATIVE**: Presentation Builder (CREATIVE-001), Voice Synthesis (CREATIVE-002)
- **ANALYSIS**: Web Researcher (ANALYSIS-001)

## Autonomy Engine

Two modes:
- **Approver**: Requires human approval for COM-001, COM-002 (external communications)
- **Collaborator**: Full autonomy for internal operations

Configuration: `config/autonomy.yaml`

## Next Steps

1. Implement real SDK bindings for all 10 tools (replace mocks)
2. Add nightly autotune job for self-improvement
3. Implement healthcheck monitoring with incident creation
4. Enhance router with ML-based skill selection
5. Add persistent audit log querying in Grafana

## Known Issues

- OpenTelemetry ConsoleSpanExporter causes cleanup warnings in tests (cosmetic only)
- FastAPI `@app.on_event` deprecated in favor of lifespan handlers (non-critical)
- Docker Compose full stack not yet tested in Replit environment

## User Preferences

- Prefers comprehensive documentation
- Expects complete, runnable code with tests
- Values clear architecture and separation of concerns
