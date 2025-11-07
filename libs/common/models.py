from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    COM = "COM"
    OPS = "OPS"
    ENG = "ENG"
    ANALYSIS = "ANALYSIS"
    CREATIVE = "CREATIVE"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    ROUTING = "routing"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"


class AutonomyMode(str, Enum):
    APPROVER = "approver"
    COLLABORATOR = "collaborator"


class TaskSpec(BaseModel):
    task_id: Optional[str] = None
    task_type: TaskType
    description: str
    context: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    autonomy_mode: AutonomyMode = AutonomyMode.COLLABORATOR
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionStep(BaseModel):
    step_id: str
    skill_id: str
    description: str
    tool: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)


class Provenance(BaseModel):
    task_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    planner_version: str = "1.0.0"
    router_decision: Optional[Dict[str, Any]] = None
    executor_logs: List[Dict[str, Any]] = Field(default_factory=list)
    validator_results: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: List[str] = Field(default_factory=list)
    retries: int = 0
    total_cost: float = 0.0
    latency_ms: float = 0.0


class AgentResult(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    artifacts: List[str] = Field(default_factory=list)
    provenance: Provenance
    error: Optional[str] = None
    draft_artifact: Optional[str] = None


class Skill(BaseModel):
    skill_id: str
    name: str
    description: str
    task_types: List[TaskType]
    tools: List[str]
    template: str
    slo_p95_ms: float = 5000.0
    cost_per_call: float = 0.01
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RoutingCandidate(BaseModel):
    skill_id: str
    score: float
    reasoning: str
    estimated_cost: float
    estimated_latency_ms: float


class RoutingDecision(BaseModel):
    task_id: str
    primary: RoutingCandidate
    alternates: List[RoutingCandidate] = Field(default_factory=list)
    benchmark_snapshot: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationResult(BaseModel):
    passed: bool
    checks: Dict[str, bool]
    failures: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UserProfile(BaseModel):
    user_id: str
    name: str
    preferences: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeBase(BaseModel):
    kb_id: str
    user_id: str
    title: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
