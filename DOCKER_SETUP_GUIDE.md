# Docker Compose Setup Guide - Complete Walkthrough

## Overview

This guide walks you through running the complete Quick2 Agent stack with Docker Compose, including all 8 microservices and infrastructure (Redis, PostgreSQL, MinIO, Prometheus, Grafana).

**Important**: This must be run on your **local machine** or a **server**, NOT inside Replit.

---

## Prerequisites

### 1. Install Docker Desktop (for Mac/Windows) or Docker Engine (for Linux)

**Mac/Windows:**
- Download from: https://www.docker.com/products/docker-desktop
- Install and start Docker Desktop
- Verify installation:
  ```bash
  docker --version
  docker-compose --version
  ```

**Linux (Ubuntu/Debian):**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Verify
docker --version
docker compose version
```

### 2. System Requirements

- **RAM**: Minimum 4GB (8GB recommended)
- **Disk**: At least 5GB free space
- **CPU**: 2+ cores recommended

---

## Step-by-Step Setup

### Step 1: Clone the Repository to Your Local Machine

```bash
# If you're starting from Replit, download the code first
# Option A: Use git clone (if pushed to GitHub)
git clone <your-github-repo-url>
cd quick2-agent

# Option B: Download as ZIP from Replit
# 1. In Replit, click the three dots menu
# 2. Select "Download as zip"
# 3. Extract and cd into the folder
```

### Step 2: Create Environment File

Create a `.env` file in the root directory:

```bash
# Copy the example
cp .env.example .env

# Or create manually:
cat > .env << 'EOF'
# Database
DATABASE_URL=postgresql://quick2:quick2pass@postgres:5432/quick2_agent
PGHOST=postgres
PGPORT=5432
PGUSER=quick2
PGPASSWORD=quick2pass
PGDATABASE=quick2_agent

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# MinIO (S3-compatible storage)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=artifacts

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Session
SESSION_SECRET=your-secret-key-change-in-production

# Service URLs
PLANNER_URL=http://planner:8001
ROUTER_URL=http://router:8002
EXECUTOR_URL=http://executor:8003
VALIDATOR_URL=http://validator:8004
MEMORY_URL=http://memory:8005
BENCHMARKS_URL=http://benchmarks:8006
EOF
```

### Step 3: Review Docker Compose Configuration

The `docker-compose.yml` file defines:
- **8 Microservices**: gateway, planner, router, executor, validator, memory, benchmarks, dashboard
- **PostgreSQL**: Database with pgvector extension
- **Redis**: Caching layer
- **MinIO**: S3-compatible object storage
- **Prometheus**: Metrics collection
- **Grafana**: Metrics visualization

You can view it:
```bash
cat docker-compose.yml
```

### Step 4: Build and Start All Services

```bash
# Build all Docker images (first time only, takes 5-10 minutes)
docker-compose build

# Start all services in detached mode
docker-compose up -d

# View logs (optional)
docker-compose logs -f
```

**What's happening:**
1. Docker builds images for all 8 services
2. Starts PostgreSQL, Redis, MinIO containers
3. Initializes databases and creates tables
4. Starts all microservices
5. Starts Prometheus and Grafana

### Step 5: Wait for Services to Start

Services need 30-60 seconds to fully initialize. Check status:

```bash
# View running containers
docker-compose ps

# All services should show "Up" or "running"
```

Expected output:
```
NAME                STATUS              PORTS
quick2-gateway      Up 30 seconds       0.0.0.0:8000->8000/tcp
quick2-planner      Up 30 seconds       8001/tcp
quick2-router       Up 30 seconds       8002/tcp
quick2-executor     Up 30 seconds       8003/tcp
quick2-validator    Up 30 seconds       8004/tcp
quick2-memory       Up 30 seconds       8005/tcp
quick2-benchmarks   Up 30 seconds       8006/tcp
quick2-dashboard    Up 30 seconds       0.0.0.0:5000->5000/tcp
postgres            Up 30 seconds       5432/tcp
redis               Up 30 seconds       6379/tcp
minio               Up 30 seconds       0.0.0.0:9000-9001->9000-9001/tcp
prometheus          Up 30 seconds       0.0.0.0:9090->9090/tcp
grafana             Up 30 seconds       0.0.0.0:3000->3000/tcp
```

### Step 6: Verify Health of All Services

```bash
# Check Gateway
curl http://localhost:8000/health

# Check Planner
curl http://localhost:8001/health

# Check Router
curl http://localhost:8002/health

# Check Executor
curl http://localhost:8003/health

# Check Validator
curl http://localhost:8004/health

# Each should return: {"status": "healthy"}
```

### Step 7: Test the Orchestration Pipeline

Submit a test task:

```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: test-$(date +%s)" \
  -d '{
    "task_type": "ENG",
    "description": "Fix failing unit tests in authentication module",
    "context": {
      "repo_url": "https://github.com/example/app"
    }
  }' | jq
```

Expected response (success):
```json
{
  "task_id": "abc123...",
  "status": "completed",
  "result": {
    "tool": "unit_test_runner",
    "status": "success",
    "result": "Tests passed: 45/50",
    "metadata": {...}
  },
  "artifacts": ["minio://artifacts/..."],
  "provenance": {...}
}
```

### Step 8: Access the Web Interfaces

Open in your browser:

| Service | URL | Credentials |
|---------|-----|-------------|
| **Gateway API** | http://localhost:8000 | N/A |
| **Dashboard** | http://localhost:5000 | N/A |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9090 | N/A |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |

### Step 9: Monitor Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f gateway
docker-compose logs -f planner

# Last 100 lines
docker-compose logs --tail=100
```

---

## Common Commands

### View Running Containers
```bash
docker-compose ps
```

### Restart a Specific Service
```bash
docker-compose restart gateway
```

### Stop All Services
```bash
docker-compose down
```

### Stop and Remove All Data (Fresh Start)
```bash
docker-compose down -v
```

### Rebuild After Code Changes
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

### View Resource Usage
```bash
docker stats
```

---

## Testing the Complete Pipeline

### Test 1: Engineering Task
```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: eng-001" \
  -d '{
    "task_type": "ENG",
    "description": "Generate unit tests for user authentication"
  }' | jq
```

### Test 2: Operations Task
```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: ops-001" \
  -d '{
    "task_type": "OPS",
    "description": "Search documentation for API rate limits"
  }' | jq
```

### Test 3: Communication Task (Approval Mode)
```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: com-001" \
  -d '{
    "task_type": "COM",
    "description": "Draft email about Q4 updates",
    "autonomy_mode": "approver"
  }' | jq
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
docker-compose logs

# Common fix: Remove old volumes and restart
docker-compose down -v
docker-compose up -d
```

### Port Already in Use

If you get "port already allocated" errors:

```bash
# Find what's using the port (Mac/Linux)
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or change ports in docker-compose.yml
```

### Database Connection Errors

```bash
# Wait longer (Postgres takes time to initialize)
sleep 30

# Check Postgres logs
docker-compose logs postgres

# Restart Postgres
docker-compose restart postgres
```

### Out of Memory

```bash
# Check resource usage
docker stats

# Increase Docker Desktop memory:
# Docker Desktop → Settings → Resources → Memory (set to 4GB+)
```

---

## Shutting Down

### Graceful Shutdown (Keeps Data)
```bash
docker-compose down
```

### Complete Cleanup (Removes All Data)
```bash
docker-compose down -v --remove-orphans
docker system prune -a
```

---

## Production Deployment

For production deployment on AWS/GCP/Azure:

1. **Use managed services** instead of containers:
   - PostgreSQL → AWS RDS or Google Cloud SQL
   - Redis → AWS ElastiCache or Upstash
   - MinIO → AWS S3 or Google Cloud Storage

2. **Deploy services** to:
   - AWS ECS/EKS
   - Google Cloud Run
   - Azure Container Instances

3. **Update environment variables** to point to managed services

4. **Enable authentication** and SSL certificates

5. **Set up monitoring** with CloudWatch, Datadog, or New Relic

---

## Summary

✅ **Step 1**: Install Docker Desktop  
✅ **Step 2**: Clone repo to local machine  
✅ **Step 3**: Create `.env` file  
✅ **Step 4**: Run `docker-compose up -d`  
✅ **Step 5**: Wait 30-60 seconds  
✅ **Step 6**: Test with curl  
✅ **Step 7**: Access Dashboard at http://localhost:5000  

Your complete orchestration system is now running! 🚀
