# Running Quick2 Agent in Replit - Alternative Guide

## Why This Guide Exists

Docker Compose **cannot run inside Replit** because Replit uses a Nix-based environment that doesn't support nested virtualization. This guide shows you how to run the orchestration system using Replit's built-in services and external managed services.

---

## Architecture in Replit

Instead of Docker containers, you'll use:

- ✅ **Replit PostgreSQL** (already available)
- ☁️ **Upstash Redis** (free managed service)
- ☁️ **Cloudflare R2 or AWS S3** (for MinIO replacement)
- 🐍 **Python processes** (services run directly)

---

## Option 1: Standalone Demo (Simplest - Already Working)

**Best for**: Demonstrations and testing the orchestration logic

```bash
python standalone_demo.py
```

**Pros**:
- ✅ No setup required
- ✅ Shows complete pipeline
- ✅ Works immediately

**Cons**:
- ❌ No persistence (in-memory only)
- ❌ No real caching
- ❌ Single-process (not distributed)

---

## Option 2: Replit + External Services (Production-Like)

**Best for**: Production-ready setup that runs in Replit

### Step 1: Set Up External Redis (Free)

1. **Sign up for Upstash Redis**:
   - Go to https://upstash.com/
   - Click "Get Started Free"
   - Create account (GitHub sign-in available)

2. **Create a Redis database**:
   - Click "Create Database"
   - Choose a region close to you
   - Select "Free" tier
   - Click "Create"

3. **Get connection details**:
   - Copy the endpoint (e.g., `us1-happy-butterfly-12345.upstash.io`)
   - Copy the port (usually `6379` or `6380`)
   - Copy the password

4. **Add to Replit Secrets**:
   - In Replit, open the "Secrets" tab (🔒 icon in sidebar)
   - Add these secrets:
     ```
     REDIS_HOST=us1-happy-butterfly-12345.upstash.io
     REDIS_PORT=6379
     REDIS_PASSWORD=your-password-here
     ```

### Step 2: Set Up Object Storage (Optional)

For artifact storage, choose one:

**Option A: Cloudflare R2 (Recommended)**
1. Sign up at https://cloudflare.com
2. Navigate to R2 Object Storage
3. Create a bucket
4. Get access keys
5. Add to Replit Secrets:
   ```
   R2_ENDPOINT=https://your-account.r2.cloudflarestorage.com
   R2_ACCESS_KEY=...
   R2_SECRET_KEY=...
   R2_BUCKET=artifacts
   ```

**Option B: AWS S3**
1. Sign up at https://aws.amazon.com
2. Create S3 bucket
3. Get IAM credentials
4. Add to Replit Secrets

### Step 3: Update Service Code for Redis Authentication

Edit `services/gateway/main.py`, `services/router/main.py`, and `services/benchmarks/main.py`:

```python
# Change from:
redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", 6379)))

# To:
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
    ssl=True,  # Upstash requires SSL
    decode_responses=True
)
```

### Step 4: Run Services

You can run services in separate terminals or use `tmux`:

**Terminal 1 - Planner:**
```bash
python services/planner/main.py
```

**Terminal 2 - Router:**
```bash
python services/router/main.py
```

**Terminal 3 - Executor:**
```bash
python services/executor/main.py
```

**Terminal 4 - Validator:**
```bash
python services/validator/main.py
```

**Terminal 5 - Gateway:**
```bash
python services/gateway/main.py
```

**Or use the demo script:**
```bash
./run_orchestration_demo.sh
```

### Step 5: Test the System

```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: test-123" \
  -d '{
    "task_type": "ENG",
    "description": "Fix failing tests"
  }'
```

---

## Comparison: Docker vs Replit

| Feature | Docker Compose | Replit + External Services |
|---------|----------------|----------------------------|
| **Setup Complexity** | Medium | Low |
| **Where to Run** | Local machine/Server | Inside Replit |
| **PostgreSQL** | Container | Built-in |
| **Redis** | Container | Upstash (managed) |
| **Object Storage** | MinIO container | Cloudflare R2 / S3 |
| **Monitoring** | Prometheus + Grafana | Dashboard service |
| **Cost** | Free (runs locally) | Free tier available |
| **Production Ready** | Yes | Yes |

---

## Recommended Approach

**For Development & Demos (in Replit):**
```bash
python standalone_demo.py
```

**For Testing the Full System (in Replit):**
1. Set up Upstash Redis (5 minutes)
2. Update Redis connection code
3. Run services with `./run_orchestration_demo.sh`

**For Production Deployment:**
1. Use Docker Compose on a cloud server (AWS EC2, DigitalOcean)
2. Or deploy to Kubernetes (AWS EKS, GKE)
3. Or use serverless (AWS Lambda, Cloud Run)

---

## Quick Start Decision Tree

```
Are you in Replit right now?
│
├─ YES → Want to see it work immediately?
│        │
│        ├─ YES → Run: python standalone_demo.py
│        │
│        └─ NO → Want production-like setup?
│                 → Set up Upstash Redis (5 min)
│                 → Run services individually
│
└─ NO → Have Docker installed on your machine?
         │
         ├─ YES → Run: docker-compose up -d
         │
         └─ NO → Install Docker Desktop first
                  → Then: docker-compose up -d
```

---

## Summary

✅ **In Replit**: Use standalone demo or connect to external Redis  
✅ **On Local Machine**: Use Docker Compose for complete stack  
✅ **In Production**: Deploy to cloud with managed services  

Choose the approach that fits your current environment!
