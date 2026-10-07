"""
Core types, enumerations, and data structures for the Windows VMM simulator.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PfnState(str, Enum):
    """Windows Page Frame Number (PFN) Database states."""
    FREE = "free"          # Frame contains uninitialized / stale data
    ZEROED = "zero"        # Frame has been zero-filled by the zero-page thread
    STANDBY = "stby"       # Clean page trimmed from working set; can be soft-faulted
    MODIFIED = "mod"       # Dirty page trimmed from working set; must be flushed before reuse
    ACTIVE = "act"         # Resident in a process working set (Valid PTE)


class PageFaultType(str, Enum):
    """Classification of page access outcomes."""
    HIT = "hit"            # Resident in working set, immediate memory access
    SOFT = "soft"          # Page on Standby or Modified list, reattached without disk I/O
    HARD = "hard"          # Page not in physical memory, fetched from disk/pagefile


class ReplacementPolicy(str, Enum):
    """Supported page replacement algorithms."""
    FIFO = "FIFO"
    LRU = "LRU"
    CLOCK = "Clock"
    OPT = "OPT"


class PageFrame(BaseModel):
    """Represents an entry in the physical Page Frame Number (PFN) database."""
    i: int                          # Physical Frame Number (PFN index 0..15)
    s: PfnState                     # PFN list / state
    p: int = -1                     # Process owner ID (0..2), or -1 if unassigned
    pg: int = -1                    # Virtual Page Number (0..9), or -1 if unassigned
    d: int = 0                      # Dirty bit (1 = modified, 0 = clean)
    u: int = 0                      # Timestamp of last access (for LRU / trimming)


class TLBEntry(BaseModel):
    """Translation Lookaside Buffer entry."""
    process_id: int
    page_number: int
    frame_number: int


class AddressTranslationResult(BaseModel):
    """Result of MMU virtual-to-physical address translation."""
    virtual_address: int
    virtual_address_hex: str
    page_number: int
    offset: int
    offset_hex: str
    tlb_hit: bool
    fault_type: PageFaultType
    frame_number: Optional[int] = None
    physical_address: Optional[int] = None
    physical_address_hex: Optional[str] = None
    message: str


class VmmStatistics(BaseModel):
    """Cumulative telemetry metrics for memory subsystem."""
    accesses: int = 0
    hit: int = 0
    soft: int = 0
    hard: int = 0
    rd: int = 0                    # Disk reads
    wr: int = 0                    # Disk writes
    tlb_hits: int = 0
    tlb_misses: int = 0
    fault_rate_pct: float = 0.0
    tlb_hit_rate_pct: float = 0.0
    soft_fault_ratio_pct: float = 0.0


class ProcessWorkingSetInfo(BaseModel):
    """Working set status for a single process."""
    process_id: int
    process_name: str
    limit: int
    active_pages: List[int]
    active_count: int
    color: str


class PageTableEntry(BaseModel):
    """Architecture PTE entry representation."""
    page_number: int
    state_label: str
    valid: bool
    frame_number: Optional[int] = None
    dirty: bool = False
    in_tlb: bool = False


class VmmStateSnapshot(BaseModel):
    """Full snapshot of the simulated Windows VMM kernel."""
    timestamp: int
    frames: List[PageFrame]
    lists: Dict[str, List[int]]
    working_sets: List[ProcessWorkingSetInfo]
    stats: VmmStatistics
    log: List[str]
    tlb: List[int]
    history: List[List[int]]
    current_process: int
    write_mode: bool
    is_thrashing: bool
