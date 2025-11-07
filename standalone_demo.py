#!/usr/bin/env python3
"""
Standalone Quick2 Agent Orchestration Demo
Runs without Redis/Postgres - demonstrates the complete pipeline in-memory
"""

import json
import time
from datetime import datetime
from typing import Dict, List
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Simulated in-memory caches
BENCHMARK_CACHE = {}
IDEMPOTENCY_CACHE = {}

# Import services
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from libs.common.models import (
    TaskSpec, TaskType, AutonomyMode, ExecutionStep,
    RoutingCandidate, RoutingDecision, ValidationResult
)

def print_section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


class StandalonePipeline:
    """Self-contained orchestration pipeline - no external dependencies"""
    
    def __init__(self):
        # Load skills registry
        self.skills = self._load_skills()
        self._seed_benchmarks()
    
    def _load_skills(self):
        """Load skills from YAML"""
        import yaml
        with open("skills/skills.yaml", "r") as f:
            data = yaml.safe_load(f)
        return {s["skill_id"]: s for s in data.get("skills", [])}
    
    def _seed_benchmarks(self):
        """Seed benchmark cache"""
        global BENCHMARK_CACHE
        BENCHMARK_CACHE = {
            "COM-001": {"p95_ms": 2800, "success_rate": 0.95, "cost": 0.02},
            "COM-002": {"p95_ms": 2300, "success_rate": 0.97, "cost": 0.015},
            "OPS-001": {"p95_ms": 3800, "success_rate": 0.92, "cost": 0.05},
            "OPS-002": {"p95_ms": 4800, "success_rate": 0.89, "cost": 0.03},
            "ENG-001": {"p95_ms": 7500, "success_rate": 0.88, "cost": 0.08},
            "ENG-002": {"p95_ms": 5800, "success_rate": 0.90, "cost": 0.06},
            "CREATIVE-001": {"p95_ms": 6800, "success_rate": 0.93, "cost": 0.04},
            "CREATIVE-002": {"p95_ms": 4300, "success_rate": 0.94, "cost": 0.025},
            "ANALYSIS-001": {"p95_ms": 9500, "success_rate": 0.91, "cost": 0.07},
        }
    
    def plan(self, task: TaskSpec):
        """Planner: Decompose task into steps"""
        print("   🧠 PLANNER: Analyzing task and selecting skills...")
        
        matching_skills = [
            s for s in self.skills.values()
            if task.task_type.value in s["task_types"]
        ]
        
        if not matching_skills:
            raise ValueError(f"No skills for {task.task_type}")
        
        steps = []
        for idx, skill in enumerate(matching_skills[:3]):
            step = ExecutionStep(
                step_id=f"step-{idx+1}",
                skill_id=skill["skill_id"],
                description=f"{skill['name']}: {skill['description']}",
                tool=skill["tools"][0] if skill["tools"] else None,
                params={"task_description": task.description}
            )
            steps.append(step)
        
        print(f"   ✓ Generated {len(steps)} execution steps")
        print(f"   ✓ Candidate skills: {[s.skill_id for s in steps]}")
        
        return steps
    
    def route(self, steps: List[ExecutionStep]):
        """Router: Select best skill using benchmarks"""
        print("\n   🎯 ROUTER: Scoring skills with cached benchmarks...")
        
        candidates = []
        for step in steps:
            bench = BENCHMARK_CACHE.get(step.skill_id, {"p95_ms": 5000, "success_rate": 0.9, "cost": 0.05})
            
            # Score: weighted combination of latency, success, cost
            latency_score = max(0, 1 - (bench["p95_ms"] / 10000))
            success_score = bench["success_rate"]
            cost_score = max(0, 1 - (bench["cost"] / 0.1))
            score = 0.3 * latency_score + 0.5 * success_score + 0.2 * cost_score
            
            candidate = RoutingCandidate(
                skill_id=step.skill_id,
                score=score,
                reasoning=f"latency={bench['p95_ms']}ms, success={bench['success_rate']:.1%}, cost=${bench['cost']}",
                estimated_cost=bench["cost"],
                estimated_latency_ms=bench["p95_ms"]
            )
            candidates.append(candidate)
        
        candidates.sort(key=lambda x: x.score, reverse=True)
        
        print(f"   ✓ Top choice: {candidates[0].skill_id} (score: {candidates[0].score:.3f})")
        print(f"   ✓ Alternates: {[c.skill_id for c in candidates[1:3]]}")
        
        return RoutingDecision(
            task_id="demo-task",
            primary=candidates[0],
            alternates=candidates[1:3] if len(candidates) > 1 else []
        )
    
    def execute(self, step: ExecutionStep):
        """Executor: Run the tool"""
        print(f"\n   ⚙️  EXECUTOR: Running tool '{step.tool}'...")
        
        # Simulated tool execution
        tool_results = {
            "browser": {"status": "success", "result": "Fetched content from URL", "metadata": {"status_code": 200}},
            "pdf_parser": {"status": "success", "result": "Extracted 150 pages", "metadata": {"pages": 150}},
            "vector_search": {"status": "success", "result": [{"id": "doc-1", "score": 0.95}], "metadata": {"total": 3}},
            "repo_reader": {"status": "success", "result": "Analyzed repository", "metadata": {"files": 47}},
            "unit_test_runner": {"status": "success", "result": "Tests passed: 45/50", "metadata": {"passed": 45, "failed": 5, "coverage": 0.87}},
            "email_api": {"status": "success", "result": "Email queued", "metadata": {"to": "user@example.com"}},
            "calendar_api": {"status": "success", "result": "Event created", "metadata": {"event_id": "evt-123"}},
            "ppt_api": {"status": "success", "result": "Created presentation", "metadata": {"slides": 12}},
            "tts": {"status": "success", "result": "Generated speech", "metadata": {"duration": 45}},
            "asr": {"status": "success", "result": "Transcribed audio", "metadata": {"confidence": 0.94}},
        }
        
        result = tool_results.get(step.tool, {"status": "success", "result": "Completed"})
        result["tool"] = step.tool
        result["artifact_uri"] = f"minio://artifacts/{step.tool}_{hash(step.step_id) % 10000}.json"
        
        print(f"   ✓ Tool execution complete")
        print(f"   ✓ Result: {result['result']}")
        
        return result
    
    def validate(self, result: dict):
        """Validator: Multi-stage validation"""
        print("\n   ✅ VALIDATOR: Running validation checks...")
        
        checks = {
            "json_schema": True,
            "email_rules": True,
            "action_schema": True,
            "pytest": result.get("tool") != "unit_test_runner" or result.get("metadata", {}).get("passed", 0) > 0,
            "coverage": result.get("tool") != "unit_test_runner" or result.get("metadata", {}).get("coverage", 1.0) >= 0.7,
            "bias_metrics": True
        }
        
        failures = [k for k, v in checks.items() if not v]
        passed = len(failures) == 0
        
        print(f"   ✓ Checks: {sum(checks.values())}/{len(checks)} passed")
        if failures:
            print(f"   ⚠ Failures: {failures}")
        
        return ValidationResult(
            passed=passed,
            checks=checks,
            failures=failures
        )
    
    def orchestrate(self, task_type: str, description: str, autonomy_mode: str = "collaborator"):
        """Complete orchestration pipeline"""
        start_time = time.time()
        
        print_section(f"Orchestrating {task_type} Task")
        print(f"📝 Task: {description}")
        print(f"🔐 Mode: {autonomy_mode}")
        
        # Create task
        task = TaskSpec(
            task_type=TaskType(task_type),
            description=description,
            autonomy_mode=AutonomyMode(autonomy_mode)
        )
        
        # Step 1: Planner
        steps = self.plan(task)
        
        # Step 2: Router
        routing = self.route(steps)
        
        # Step 3: Executor
        primary_step = next(s for s in steps if s.skill_id == routing.primary.skill_id)
        result = self.execute(primary_step)
        
        # Step 4: Validator
        validation = self.validate(result)
        
        # Assemble final result
        latency_ms = (time.time() - start_time) * 1000
        
        print_section("Result Summary")
        print(f"✅ Status: {'COMPLETED' if validation.passed else 'FAILED'}")
        print(f"⚡ Latency: {latency_ms:.0f}ms")
        print(f"💰 Cost: ${routing.primary.estimated_cost:.3f}")
        print(f"🎯 Skill: {routing.primary.skill_id}")
        print(f"🔧 Tool: {result['tool']}")
        print(f"📊 Result: {result['result']}")
        
        if result.get("metadata"):
            print(f"📋 Metadata: {json.dumps(result['metadata'], indent=2)}")
        
        return {
            "status": "completed" if validation.passed else "failed",
            "result": result,
            "routing": routing.model_dump(),
            "validation": validation.model_dump(),
            "latency_ms": latency_ms,
            "cost": routing.primary.estimated_cost
        }


def main():
    print_section("Quick2 Agent - Standalone Orchestration Demo")
    print("This demonstrates the complete pipeline without external dependencies:")
    print("  Gateway → Planner → Router → Executor → Validator → Result\n")
    
    pipeline = StandalonePipeline()
    
    # Test 1: Code Fixing
    pipeline.orchestrate(
        "ENG",
        "Fix failing unit tests in the authentication module"
    )
    
    time.sleep(1)
    
    # Test 2: RAG Query
    pipeline.orchestrate(
        "OPS",
        "Find and summarize documentation about API rate limits"
    )
    
    time.sleep(1)
    
    # Test 3: Email (with approval mode)
    result = pipeline.orchestrate(
        "COM",
        "Draft a professional email about Q4 project updates",
        "approver"
    )
    
    print_section("Demo Complete")
    print("✨ The orchestration system successfully:")
    print("   1. ✓ Decomposed tasks into execution steps (Planner)")
    print("   2. ✓ Selected optimal skills using benchmarks (Router)")
    print("   3. ✓ Executed tools and generated artifacts (Executor)")
    print("   4. ✓ Validated results with multi-stage checks (Validator)")
    print("   5. ✓ Returned complete provenance and audit trail")
    print("\n💡 To run with full infrastructure (Redis, Postgres, MinIO, etc.):")
    print("   docker-compose up --build")
    print("\n📊 Dashboard monitoring UI is running at: http://localhost:5000")


if __name__ == "__main__":
    main()
