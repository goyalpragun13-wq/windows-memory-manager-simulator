"""
Educational scenarios API routes.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_kernel
from app.core.vmm import WindowsMemoryManager
from app.core.workloads import SCENARIO_CONFIGS, build_scenario_steps
from app.schemas.scenarios import ScenarioInfo, ScenarioRunResponse

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


@router.get("", response_model=List[ScenarioInfo])
def list_scenarios():
    """Retrieve catalog of educational memory manager scenarios."""
    return [ScenarioInfo(**c) for c in SCENARIO_CONFIGS]


@router.post("/{scenario_id}/run", response_model=ScenarioRunResponse)
def execute_scenario(
    scenario_id: int,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """
    Load and execute an educational scenario.
    Resets the simulator, applies scenario working-set quotas, replays workload,
    and returns verification assertions against expected counters.
    """
    config = next((c for c in SCENARIO_CONFIGS if c["id"] == scenario_id), None)
    if not config:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found.")

    # Reset simulator with scenario working set limits
    kernel.reset(limits=config["working_set_limits"])
    steps = build_scenario_steps(scenario_id)

    for step in steps:
        if step[0] == "kill":
            kernel.terminate_process(step[1])
        elif step[0] == "flush":
            kernel.flush_modified_pages()
        else:
            kernel.access_page(step[0], step[1], bool(step[2]))

    actual_counters = {
        "hit": kernel.stats.hit,
        "soft": kernel.stats.soft,
        "hard": kernel.stats.hard,
        "wr": kernel.stats.wr,
    }
    passed = (actual_counters == config["expected_counters"])

    return ScenarioRunResponse(
        scenario=ScenarioInfo(**config),
        executed_steps=len(steps),
        final_counters=actual_counters,
        verification_passed=passed,
        message=f"Scenario '{config['name']}' executed successfully. Verification: {'PASSED' if passed else 'FAILED'}."
    )
