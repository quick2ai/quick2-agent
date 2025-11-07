# Quick2 Agent Orchestration Guide

## What You're Looking At

**Dashboard (Port 5000)** = Monitoring UI showing metrics
**Gateway (Port 8000)** = The actual orchestration app that processes tasks

## Understanding the Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER SUBMITS TASK                          │
│                    POST /v1/tasks                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  GATEWAY (Port 8000) - Orchestration Engine                     │
│  - Validates idempotency                                        │
│  - Checks autonomy mode (Approver vs Collaborator)              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  PLANNER (Port 8001) - Task Decomposition                       │
│  - Loads skills.yaml registry (9 skills)                        │
│  - Matches task type to skills                                  │
│  - Generates execution steps                                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  ROUTER (Port 8002) - Benchmark-Based Selection                 │
│  - Fetches cached benchmarks from Redis                         │
│  - Scores candidates by: latency, success rate, cost            │
│  - Returns: Top-1 + 2 alternates                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  EXECUTOR (Port 8003) - Tool Execution                          │
│  - Runs 10 tools: browser, pdf_parser, vector_search,          │
│    repo_reader, unit_test_runner, email_api, calendar_api,     │
│    ppt_api, tts, asr                                            │
│  - Returns artifact URIs (MinIO references)                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  VALIDATOR (Port 8004) - Multi-Stage Validation                 │
│  - JSONSchema check                                             │
│  - Email rules validation                                       │
│  - Action schema verification                                   │
│  - Pytest runner (for code tasks)                               │
│  - Coverage check                                               │
│  - Bias metrics                                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  GATEWAY - Result Assembly                                      │
│  - Builds AgentResult with provenance                           │
│  - Writes audit log to MinIO                                    │
│  - Caches result for idempotency                                │
│  - Returns complete result + metadata to user                   │
└─────────────────────────────────────────────────────────────────┘
```

## How to Use the Orchestration

### Option 1: Run the Demo Script

```bash
chmod +x run_orchestration_demo.sh
./run_orchestration_demo.sh
```

This will:
1. Start all 5 core services (Gateway, Planner, Router, Executor, Validator)
2. Submit 3 sample tasks showing different flows
3. Display the orchestration results

### Option 2: Manual API Testing

**Start all services:**
```bash
# Terminal 1: Planner
python services/planner/main.py

# Terminal 2: Router  
python services/router/main.py

# Terminal 3: Executor
python services/executor/main.py

# Terminal 4: Validator
python services/validator/main.py

# Terminal 5: Gateway
python services/gateway/main.py
```

**Submit a task via API:**
```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: test-123" \
  -d '{
    "task_type": "ENG",
    "description": "Fix failing unit tests",
    "autonomy_mode": "collaborator"
  }' | jq
```

**Example Response:**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "result": {
    "tool": "unit_test_runner",
    "status": "success",
    "result": "Tests passed: 45/50",
    "metadata": {
      "passed": 45,
      "failed": 5,
      "coverage": 0.87
    }
  },
  "artifacts": ["minio://artifacts/test_results_1234.xml"],
  "provenance": {
    "task_id": "abc-123",
    "planner_version": "1.0.0",
    "router_decision": {
      "primary": {
        "skill_id": "ENG-001",
        "score": 0.92,
        "estimated_cost": 0.08
      }
    },
    "latency_ms": 7500,
    "total_cost": 0.08
  }
}
```

### Option 3: Docker Compose (Full Stack)

```bash
docker-compose up --build
```

This starts all 8 services + infrastructure (Redis, Postgres, MinIO, Prometheus, Grafana).

## Task Examples

### 1. Code Fixing (ENG-001)
```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: eng-$(date +%s)" \
  -d '{
    "task_type": "ENG",
    "description": "Fix failing authentication tests",
    "context": {
      "repo_url": "https://github.com/example/app",
      "test_path": "tests/test_auth.py"
    }
  }'
```

### 2. RAG Query (OPS-001)
```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: ops-$(date +%s)" \
  -d '{
    "task_type": "OPS",
    "description": "Find documentation about rate limits",
    "context": {
      "query": "API rate limiting best practices"
    }
  }'
```

### 3. Email (COM-001) - Requires Approval
```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: com-$(date +%s)" \
  -d '{
    "task_type": "COM",
    "description": "Draft email about Q4 updates",
    "autonomy_mode": "approver"
  }'
```

Returns `"status": "awaiting_approval"` with a draft artifact.

## What Makes This an "Orchestration" System

1. **Task Planning**: Automatically selects the right skills based on task type
2. **Intelligent Routing**: Chooses the best skill using cached benchmarks
3. **Multi-Tool Execution**: Runs complex tools (code analysis, web scraping, etc.)
4. **Automated Validation**: Multi-stage checks ensure quality
5. **Provenance Tracking**: Full audit trail of every decision
6. **Autonomy Control**: Approver mode for sensitive operations

## Monitoring

- **Dashboard**: http://localhost:5000 - Real-time metrics
- **Prometheus**: http://localhost:9090 - Raw metrics
- **Grafana**: http://localhost:3000 - Advanced visualizations (admin/admin)

## Currently Running

The **Dashboard (port 5000)** is showing you the monitoring view. To see the orchestration in action, you need to:

1. Start the other services (Gateway, Planner, Router, Executor, Validator)
2. Submit tasks via the Gateway API
3. Watch the results flow through the pipeline
4. See metrics update in real-time on the Dashboard

The Dashboard shows what happened - the Gateway API is where tasks actually get orchestrated!
