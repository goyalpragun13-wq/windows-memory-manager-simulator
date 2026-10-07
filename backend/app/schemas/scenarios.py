"""
Pydantic API schemas for educational scenarios.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel


class ScenarioInfo(BaseModel):
    id: int
    name: str
    description: str
    working_set_limits: List[int]
    expected_counters: Dict[str, int]


class ScenarioRunResponse(BaseModel):
    scenario: ScenarioInfo
    executed_steps: int
    final_counters: Dict[str, int]
    verification_passed: bool
    message: str
