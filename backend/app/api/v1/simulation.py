"""
Simulation lifecycle and memory operation endpoints.
"""

import random
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_kernel
from app.core.vmm import WindowsMemoryManager
from app.core.types import VmmStateSnapshot
from app.schemas.simulation import (
    AccessPageRequest,
    SetWorkingSetLimitRequest,
    ResetSimulationRequest,
    AutoStepRequest,
)

router = APIRouter(prefix="/sim", tags=["Simulation"])


@router.get("/state", response_model=VmmStateSnapshot)
def get_simulation_state(kernel: WindowsMemoryManager = Depends(get_kernel)):
    """Retrieve full snapshot of the Windows VMM simulator."""
    return kernel.get_snapshot()


@router.post("/access")
def access_memory_page(
    req: AccessPageRequest,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """
    Access a virtual page for a process.
    Simulates cache hit, soft page fault, or hard page fault.
    """
    fault_type, frame = kernel.access_page(req.process_id, req.page_number, req.is_write)
    return {
        "fault_type": fault_type.value,
        "frame": frame.model_dump(),
        "state": kernel.get_snapshot().model_dump(),
    }


@router.post("/process/{process_id}")
def select_current_process(
    process_id: int,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """Set the currently focused process in the UI (0..2)."""
    if not (0 <= process_id <= 2):
        raise HTTPException(status_code=400, detail="Process ID must be 0, 1, or 2.")
    kernel.current_process = process_id
    return {"current_process": kernel.current_process}


@router.post("/mode/toggle")
def toggle_write_mode(kernel: WindowsMemoryManager = Depends(get_kernel)):
    """Toggle between Read mode and Write mode (marks accessed pages dirty)."""
    kernel.write_mode = not kernel.write_mode
    return {"write_mode": kernel.write_mode}


@router.post("/flush")
def trigger_modified_page_writer(kernel: WindowsMemoryManager = Depends(get_kernel)):
    """
    Trigger the Modified Page Writer to flush all dirty pages from the
    Modified list to the pagefile, resetting dirty bits and moving them to Standby.
    """
    flushed_count = kernel.flush_modified_pages()
    return {
        "flushed_count": flushed_count,
        "state": kernel.get_snapshot().model_dump(),
    }


@router.post("/zero-step")
def trigger_zero_page_thread(kernel: WindowsMemoryManager = Depends(get_kernel)):
    """Run one step of the idle-priority zero-page thread."""
    frame_id = kernel.pfn_db.step_zero_page_thread()
    return {
        "converted_frame_id": frame_id,
        "state": kernel.get_snapshot().model_dump(),
    }


@router.post("/kill/{process_id}")
def terminate_process(
    process_id: int,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """
    Terminate a process: flushes its TLB entries and reclaims all physical
    frames back to the Free list.
    """
    if not (0 <= process_id <= 2):
        raise HTTPException(status_code=400, detail="Process ID must be 0, 1, or 2.")
    reclaimed = kernel.terminate_process(process_id)
    return {
        "process_id": process_id,
        "reclaimed_frames": reclaimed,
        "state": kernel.get_snapshot().model_dump(),
    }


@router.post("/limit")
def set_working_set_limit(
    req: SetWorkingSetLimitRequest,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """Adjust the Working Set quota limit for a process (1..8 pages)."""
    kernel.set_working_set_limit(req.process_id, req.limit)
    return {
        "process_id": req.process_id,
        "limit": req.limit,
        "state": kernel.get_snapshot().model_dump(),
    }


@router.post("/reset")
def reset_simulation(
    req: ResetSimulationRequest = None,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """Reset the entire simulator to fresh boot state."""
    limits = req.limits if req else None
    kernel.reset(limits=limits)
    return {
        "message": "Simulation reset successfully.",
        "state": kernel.get_snapshot().model_dump(),
    }


@router.post("/step")
def simulate_auto_workload_step(
    req: AutoStepRequest = None,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """
    Simulate one or more stochastic workload access steps across processes
    using temporal locality clustering.
    """
    count = req.count if req else 1
    events = []
    for _ in range(count):
        proc = random.randint(0, 2)
        hot = kernel.hot_pages[proc]
        if random.random() < 0.1:
            base = random.randint(0, 7)
            kernel.hot_pages[proc] = [base, base + 1, base + 2]
            hot = kernel.hot_pages[proc]

        page = random.choice(hot) if random.random() < 0.8 else random.randint(0, 9)
        is_write = random.random() < 0.3
        fault, frame = kernel.access_page(proc, page, is_write)
        events.append({
            "process_id": proc,
            "page_number": page,
            "is_write": is_write,
            "fault_type": fault.value,
            "frame_id": frame.i
        })

    return {
        "steps_simulated": count,
        "events": events,
        "state": kernel.get_snapshot().model_dump(),
    }
