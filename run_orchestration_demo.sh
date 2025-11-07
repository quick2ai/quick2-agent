#!/bin/bash
# Quick2 Agent Orchestration Demo
# Starts all services and demonstrates the full pipeline

echo "🚀 Starting Quick2 Agent Microservices..."
echo ""

# Start all services in background
echo "Starting Planner service (port 8001)..."
python services/planner/main.py > /tmp/planner.log 2>&1 &
PLANNER_PID=$!

echo "Starting Router service (port 8002)..."
python services/router/main.py > /tmp/router.log 2>&1 &
ROUTER_PID=$!

echo "Starting Executor service (port 8003)..."
python services/executor/main.py > /tmp/executor.log 2>&1 &
EXECUTOR_PID=$!

echo "Starting Validator service (port 8004)..."
python services/validator/main.py > /tmp/validator.log 2>&1 &
VALIDATOR_PID=$!

echo "Starting Gateway service (port 8000)..."
python services/gateway/main.py > /tmp/gateway.log 2>&1 &
GATEWAY_PID=$!

echo ""
echo "⏳ Waiting for services to start..."
sleep 5

echo ""
echo "✅ All services running!"
echo ""
echo "📡 Service URLs:"
echo "   Gateway (Orchestrator):  http://localhost:8000"
echo "   Planner:                 http://localhost:8001"
echo "   Router:                  http://localhost:8002"
echo "   Executor:                http://localhost:8003"
echo "   Validator:               http://localhost:8004"
echo "   Dashboard (Monitoring):  http://localhost:5000"
echo ""
echo "🎯 Running orchestration demo..."
echo ""

# Run the demo
python test_orchestration.py

echo ""
echo "🛑 Stopping services..."
kill $PLANNER_PID $ROUTER_PID $EXECUTOR_PID $VALIDATOR_PID $GATEWAY_PID 2>/dev/null

echo "✨ Demo complete!"
