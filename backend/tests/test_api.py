"""
Integration tests for FastAPI endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verify API health probe responds with 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_simulation_lifecycle_api():
    """Verify reset, access, limit adjustment, and flush endpoints."""
    # Reset
    res_reset = client.post("/api/v1/sim/reset")
    assert res_reset.status_code == 200

    # Access page 0 for process 0
    res_access = client.post(
        "/api/v1/sim/access",
        json={"process_id": 0, "page_number": 0, "is_write": False}
    )
    assert res_access.status_code == 200
    data = res_access.json()
    assert data["fault_type"] == "hard"
    assert data["state"]["stats"]["hard"] == 1

    # Access again -> hit
    res_hit = client.post(
        "/api/v1/sim/access",
        json={"process_id": 0, "page_number": 0, "is_write": False}
    )
    assert res_hit.status_code == 200
    assert res_hit.json()["fault_type"] == "hit"


def test_mmu_translation_api():
    """Verify MMU translation endpoint decomposes address and returns PA."""
    res = client.post(
        "/api/v1/mmu/translate",
        json={"virtual_address": "0x2A3C", "process_id": 0, "is_write": False}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["page_number"] == 2
    assert data["offset"] == 0xA3C
    assert data["physical_address"] is not None


def test_scenarios_api():
    """Verify scenarios listing and execution of Scenario 1 (Good Locality)."""
    res_list = client.get("/api/v1/scenarios")
    assert res_list.status_code == 200
    scenarios = res_list.json()
    assert len(scenarios) == 6

    res_run = client.post("/api/v1/scenarios/1/run")
    assert res_run.status_code == 200
    data = res_run.json()
    assert data["verification_passed"] is True
    assert data["final_counters"]["hit"] == 28


def test_algorithms_lab_api():
    """Verify replacement algorithms experiment lab endpoint."""
    res = client.post(
        "/api/v1/algorithms/lab",
        json={"workload": "bel", "frame_min": 1, "frame_max": 5}
    )
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert "FIFO" in data["results"]
    assert len(data["belady_anomalies"]) > 0


def test_telemetry_self_test_runner():
    """Verify self-test suite endpoint executes all assertions with 100% pass."""
    res = client.post("/api/v1/telemetry/tests/run")
    assert res.status_code == 200
    data = res.json()
    assert data["total_tests"] >= 15
    assert data["failed_tests"] == 0
    assert data["success_rate_pct"] == 100.0
