"""
Pydantic API schemas for the replacement algorithms experiment lab.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class LabExperimentRequest(BaseModel):
    workload: str = Field(
        default="bel",
        description="Workload type: 'loc' (locality), 'loop', 'rnd' (random), 'bel' (Belady), 'ses' (session trace), or 'cus' (custom)"
    )
    custom_string: Optional[str] = Field(
        default="",
        description="Space- or comma-separated integers for custom reference string"
    )
    frame_min: int = Field(default=1, ge=1, le=16)
    frame_max: int = Field(default=10, ge=1, le=16)


class BeladyAnomalyInfo(BaseModel):
    from_frames: int
    to_frames: int
    faults_before: int
    faults_after: int


class LabExperimentResponse(BaseModel):
    workload: str
    trace_length: int
    frame_range: List[int]
    results: Dict[str, List[int]]
    belady_anomalies: List[BeladyAnomalyInfo]
    summary_message: str


class BaselinePolicyMetrics(BaseModel):
    reads: int
    writes: int


class BaselineCompareResponse(BaseModel):
    access_count: int
    windows_model: BaselinePolicyMetrics
    global_fifo: BaselinePolicyMetrics
    global_lru: BaselinePolicyMetrics
