"""
Pydantic API request and response schemas for memory simulation endpoints.
"""

from typing import Optional, List, Union
from pydantic import BaseModel, Field


class AccessPageRequest(BaseModel):
    process_id: int = Field(ge=0, le=2, description="Target process index 0..2")
    page_number: int = Field(ge=0, le=9, description="Virtual page number 0..9")
    is_write: bool = Field(default=False, description="True for write access (marks page dirty)")


class TranslateAddressRequest(BaseModel):
    virtual_address: Union[int, str] = Field(
        description="Virtual address as integer or hex string (e.g., '0x2A3C')"
    )
    process_id: Optional[int] = Field(default=None, ge=0, le=2)
    is_write: Optional[bool] = Field(default=None)


class SetWorkingSetLimitRequest(BaseModel):
    process_id: int = Field(ge=0, le=2)
    limit: int = Field(ge=1, le=8, description="New quota limit (1..8 pages)")


class ResetSimulationRequest(BaseModel):
    limits: Optional[List[int]] = Field(default=None, description="Optional custom working set quotas [p1, p2, p3]")


class AutoStepRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=100, description="Number of synthetic access steps to simulate")
