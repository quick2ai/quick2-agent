import pytest
from fastapi.testclient import TestClient


def test_planner_health():
    from services.planner.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "planner"


def test_router_health():
    from services.router.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "router"


def test_executor_health():
    from services.executor.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "executor"


def test_validator_health():
    from services.validator.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "validator"


def test_memory_health():
    from services.memory.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "memory"


def test_benchmarks_health():
    from services.benchmarks.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "benchmarks"


def test_dashboard_health():
    from services.dashboard.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "dashboard"


def test_gateway_health():
    from services.gateway.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "gateway"


def test_executor_tools():
    from services.executor.main import app
    client = TestClient(app)
    response = client.get("/v1/tools")
    assert response.status_code == 200
    tools = response.json()["tools"]
    assert "browser" in tools
    assert "pdf_parser" in tools
    assert "vector_search" in tools
    assert len(tools) == 10
