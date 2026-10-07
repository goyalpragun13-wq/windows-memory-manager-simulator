"""
Page replacement algorithms and experiment lab API routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_kernel
from app.core.vmm import WindowsMemoryManager
from app.core.algorithms import run_experiment_lab, replay_global_baseline
from app.core.workloads import generate_trace
from app.schemas.algorithms import (
    LabExperimentRequest,
    LabExperimentResponse,
    BeladyAnomalyInfo,
    BaselineCompareResponse,
    BaselinePolicyMetrics,
)

router = APIRouter(prefix="/algorithms", tags=["Page Replacement Algorithms"])


@router.post("/lab", response_model=LabExperimentResponse)
def execute_experiment_lab(
    req: LabExperimentRequest,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """
    Run FIFO, LRU, Clock, and Optimal (Belady MIN) across physical frame sweeps (1..10).
    Identifies occurrences of Belady's Anomaly where FIFO page faults increase with frame size.
    """
    if req.workload == "ses":
        # Extract reference trace from current simulator session
        trace = [p * 100 + pg for p, pg, _ in kernel.trace]
        if not trace:
            raise HTTPException(
                status_code=400,
                detail="No memory accesses recorded in current simulator session yet. Access pages first or choose another workload."
            )
    else:
        trace = generate_trace(req.workload, req.custom_string or "")
        if not trace:
            raise HTTPException(
                status_code=400,
                detail="Custom reference string is empty or invalid. Provide space-separated integers."
            )

    frames = list(range(req.frame_min, req.frame_max + 1))
    lab_data = run_experiment_lab(trace, frames)

    anomalies = [BeladyAnomalyInfo(**a) for a in lab_data["belady_anomalies"]]
    if anomalies:
        first = anomalies[0]
        summary = (
            f"Belady's Anomaly detected! FIFO page faults increased from {first.faults_before} to "
            f"{first.faults_after} when physical frames increased from {first.from_frames} to {first.to_frames}. "
            "Optimal (OPT) establishes the theoretical lower fault bound across all configurations."
        )
    else:
        summary = (
            "Experiment completed. Optimal (OPT) strictly achieves the lowest or equal fault count. "
            "No FIFO Belady anomaly was observed for this workload configuration."
        )

    return LabExperimentResponse(
        workload=req.workload,
        trace_length=len(trace),
        frame_range=frames,
        results=lab_data["results"],
        belady_anomalies=anomalies,
        summary_message=summary
    )


@router.get("/compare", response_model=BaselineCompareResponse)
def compare_windows_vs_global(kernel: WindowsMemoryManager = Depends(get_kernel)):
    """
    Replay current simulation session trace on a traditional single global pool
    (16 frames) comparing Windows two-tier VMM vs unmanaged Global FIFO and LRU.
    """
    baseline = replay_global_baseline(kernel.trace, total_frames=16)

    return BaselineCompareResponse(
        access_count=len(kernel.trace),
        windows_model=BaselinePolicyMetrics(
            reads=kernel.stats.rd,
            writes=kernel.stats.wr
        ),
        global_fifo=BaselinePolicyMetrics(
            reads=baseline["FIFO"]["reads"],
            writes=baseline["FIFO"]["writes"]
        ),
        global_lru=BaselinePolicyMetrics(
            reads=baseline["LRU"]["reads"],
            writes=baseline["LRU"]["writes"]
        )
    )
