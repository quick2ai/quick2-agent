import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from libs.common.models import ValidationResult

app = FastAPI(title="Validator Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)


class ValidationRequest(BaseModel):
    result: Dict[str, Any]
    constraints: Dict[str, Any] = {}
    task_type: str = "ANALYSIS"


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "validator"}


def validate_json_schema(data: dict, schema: dict = None) -> tuple[bool, list]:
    """Stub JSON schema validation"""
    failures = []
    
    if not isinstance(data, dict):
        failures.append("Result must be a dictionary")
        return False, failures
    
    if "status" not in data:
        failures.append("Missing required field: status")
    
    return len(failures) == 0, failures


def validate_email_rules(data: dict) -> tuple[bool, list]:
    """Stub email validation rules"""
    failures = []
    
    if data.get("tool") == "email_api":
        metadata = data.get("metadata", {})
        
        if not metadata.get("to"):
            failures.append("Email missing 'to' address")
        
        if not metadata.get("subject"):
            failures.append("Email missing subject")
        
        to = metadata.get("to", "")
        if "@" not in to:
            failures.append("Invalid email address format")
    
    return len(failures) == 0, failures


def validate_action_schema(data: dict) -> tuple[bool, list]:
    """Stub action schema validation"""
    failures = []
    
    if data.get("tool") in ["email_api", "calendar_api"]:
        if data.get("status") != "success":
            failures.append("External action did not complete successfully")
    
    return len(failures) == 0, failures


def validate_pytest_runner(data: dict) -> tuple[bool, list]:
    """Stub pytest validation"""
    failures = []
    
    if data.get("tool") == "unit_test_runner":
        metadata = data.get("metadata", {})
        passed = metadata.get("passed", 0)
        failed = metadata.get("failed", 0)
        
        if failed > passed * 0.2:
            failures.append(f"Too many test failures: {failed}/{passed + failed}")
    
    return len(failures) == 0, failures


def validate_coverage(data: dict) -> tuple[bool, list]:
    """Stub coverage check"""
    failures = []
    warnings = []
    
    if data.get("tool") == "unit_test_runner":
        metadata = data.get("metadata", {})
        coverage = metadata.get("coverage", 0)
        
        if coverage < 0.7:
            failures.append(f"Coverage too low: {coverage:.1%} < 70%")
        elif coverage < 0.8:
            warnings.append(f"Coverage below recommended: {coverage:.1%} < 80%")
    
    return len(failures) == 0, (failures, warnings)


def validate_bias_metrics(data: dict) -> tuple[bool, list]:
    """Stub bias metrics validation"""
    failures = []
    warnings = []
    
    result_text = str(data.get("result", ""))
    
    bias_keywords = ["always", "never", "definitely", "impossible"]
    found_bias = [kw for kw in bias_keywords if kw in result_text.lower()]
    
    if found_bias:
        warnings.append(f"Potential bias detected: {', '.join(found_bias)}")
    
    return True, (failures, warnings)


@app.post("/v1/validate")
async def validate(request: ValidationRequest):
    result = request.result
    checks = {}
    all_failures = []
    all_warnings = []
    
    schema_passed, schema_failures = validate_json_schema(result)
    checks["json_schema"] = schema_passed
    all_failures.extend(schema_failures)
    
    email_passed, email_failures = validate_email_rules(result)
    checks["email_rules"] = email_passed
    all_failures.extend(email_failures)
    
    action_passed, action_failures = validate_action_schema(result)
    checks["action_schema"] = action_passed
    all_failures.extend(action_failures)
    
    pytest_passed, pytest_failures = validate_pytest_runner(result)
    checks["pytest"] = pytest_passed
    all_failures.extend(pytest_failures)
    
    coverage_passed, (cov_failures, cov_warnings) = validate_coverage(result)
    checks["coverage"] = coverage_passed
    all_failures.extend(cov_failures)
    all_warnings.extend(cov_warnings)
    
    bias_passed, (bias_failures, bias_warnings) = validate_bias_metrics(result)
    checks["bias_metrics"] = bias_passed
    all_failures.extend(bias_failures)
    all_warnings.extend(bias_warnings)
    
    validation_result = ValidationResult(
        passed=all(checks.values()),
        checks=checks,
        failures=all_failures,
        warnings=all_warnings,
        metadata={"total_checks": len(checks)}
    )
    
    return validation_result.model_dump()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8004"))
    uvicorn.run(app, host="0.0.0.0", port=port)
