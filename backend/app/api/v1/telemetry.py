"""
Telemetry, statistics, test runner, and export/import endpoints.
"""

from fastapi import APIRouter, Depends
from app.api.deps import get_kernel
from app.core.vmm import WindowsMemoryManager
from app.services.test_runner import SimulationTestRunner, TestSuiteReport

router = APIRouter(prefix="/telemetry", tags=["Telemetry & Verification"])


@router.get("/stats")
def get_system_telemetry(kernel: WindowsMemoryManager = Depends(get_kernel)):
    """Retrieve runtime memory metrics and thrashing indicator."""
    return {
        "stats": kernel.stats.model_dump(),
        "is_thrashing": kernel.is_thrashing(),
        "trace_length": len(kernel.trace),
        "history": kernel.history,
    }


@router.get("/log")
def get_system_event_log(kernel: WindowsMemoryManager = Depends(get_kernel)):
    """Retrieve kernel event ring-buffer log."""
    return {"log": kernel.log}


@router.post("/tests/run", response_model=TestSuiteReport)
def execute_self_test_suite():
    """
    Execute full automated verification test suite.
    Validates algorithm implementations against Belady string, OPT minimality,
    scenario counter parity, physical frame conservation, and TLB residency.
    """
    return SimulationTestRunner.run_all()


@router.get("/export")
def export_session_trace(kernel: WindowsMemoryManager = Depends(get_kernel)):
    """
    Export current simulator state and access trace to JSON format
    for lab grading and academic reproducibility.
    """
    return {
        "snapshot": kernel.get_snapshot().model_dump(),
        "trace": [
            {"process_id": p, "page_number": pg, "is_write": bool(w)}
            for p, pg, w in kernel.trace
        ],
    }
