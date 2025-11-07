#!/usr/bin/env python3
"""
Demo script to test the Quick2 Agent orchestration pipeline.
Shows how tasks flow through: Gateway -> Planner -> Router -> Executor -> Validator
"""

import httpx
import json
import time
from datetime import datetime

GATEWAY_URL = "http://localhost:8000"


def print_section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def submit_task(task_type, description, autonomy_mode="collaborator"):
    """Submit a task to the gateway and get the orchestrated result"""
    print(f"📤 Submitting {task_type} task: {description[:50]}...")
    
    task_data = {
        "task_type": task_type,
        "description": description,
        "autonomy_mode": autonomy_mode,
        "context": {},
        "constraints": {}
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Idempotency-Key": f"test-{task_type}-{int(time.time())}"
    }
    
    try:
        response = httpx.post(
            f"{GATEWAY_URL}/v1/tasks",
            json=task_data,
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Task completed: {result['task_id']}")
        print(f"   Status: {result['status']}")
        print(f"   Latency: {result['provenance']['latency_ms']:.0f}ms")
        print(f"   Cost: ${result['provenance']['total_cost']:.3f}")
        
        if result.get('status') == 'awaiting_approval':
            print(f"   ⏸️  Requires approval - draft at: {result.get('draft_artifact')}")
        
        return result
        
    except httpx.HTTPError as e:
        print(f"❌ Error: {e}")
        return None


def main():
    print_section("Quick2 Agent Orchestration Demo")
    print("This demonstrates the full pipeline:")
    print("  Gateway → Planner → Router → Executor → Validator → Result\n")
    
    # Test 1: Engineering task (code fix)
    print_section("Test 1: ENG-001 - Code Fixer")
    result1 = submit_task(
        "ENG",
        "Fix failing unit tests in the authentication module",
        "collaborator"
    )
    if result1:
        print(f"\n📊 Result Summary:")
        print(f"   Tool used: {result1['result']['tool']}")
        print(f"   Tests passed: {result1['result']['metadata']['passed']}/{result1['result']['metadata']['passed'] + result1['result']['metadata']['failed']}")
        print(f"   Coverage: {result1['result']['metadata']['coverage']:.1%}")
    
    time.sleep(1)
    
    # Test 2: Operations task (RAG query)
    print_section("Test 2: OPS-001 - RAG Query Engine")
    result2 = submit_task(
        "OPS",
        "Find and summarize documentation about API rate limits",
        "collaborator"
    )
    if result2:
        print(f"\n📊 Result Summary:")
        print(f"   Tool used: {result2['result']['tool']}")
        print(f"   Results found: {len(result2['result']['result'])}")
        for i, doc in enumerate(result2['result']['result'][:2], 1):
            print(f"   Doc {i}: {doc['text'][:60]}... (score: {doc['score']})")
    
    time.sleep(1)
    
    # Test 3: Communication task (email - requires approval)
    print_section("Test 3: COM-001 - Email Composer (Approval Required)")
    result3 = submit_task(
        "COM",
        "Draft a professional email about Q4 project updates",
        "approver"  # This requires approval
    )
    if result3:
        print(f"\n📊 Result Summary:")
        print(f"   This task requires approval before execution")
        print(f"   Draft artifact ready for review")
    
    print_section("Demo Complete")
    print("✨ The orchestration pipeline successfully:")
    print("   1. Decomposed tasks into execution steps (Planner)")
    print("   2. Selected optimal skills using benchmarks (Router)")
    print("   3. Executed tools and generated artifacts (Executor)")
    print("   4. Validated results with multi-stage checks (Validator)")
    print("   5. Returned complete provenance and audit trail (Gateway)")
    print("\nView real-time metrics at: http://localhost:5000 (Dashboard)")


if __name__ == "__main__":
    main()
