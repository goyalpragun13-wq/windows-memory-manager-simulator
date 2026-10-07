"""
Working Set Manager for Windows processes.
Manages per-process working set quotas, residency lists, and trimming policy.
"""

from typing import List, Tuple
from app.config import NUM_PROCESSES, DEFAULT_WORKING_SET_LIMITS, PROCESS_NAMES, PROCESS_COLORS
from app.core.types import PageFrame, PfnState, ProcessWorkingSetInfo
from app.core.pfn_database import PfnDatabase
from app.core.mmu import TLB


class WorkingSetManager:
    """
    Manages process working set quotas and age-based Working Set Trimming.
    """

    def __init__(self, limits: List[int] = None):
        self.limits = list(limits or DEFAULT_WORKING_SET_LIMITS)

    def reset(self) -> None:
        """Reset limits to default."""
        self.limits = list(DEFAULT_WORKING_SET_LIMITS)

    def set_limit(self, process_id: int, new_limit: int, pfn_db: PfnDatabase, tlb: TLB) -> List[Tuple[PageFrame, str]]:
        """
        Adjust working set limit for a process (clamped between 1 and 8).
        Trims working set if current residency exceeds new limit.
        """
        clamped = max(1, min(8, new_limit))
        self.limits[process_id] = clamped
        return self.trim_working_set(process_id, pfn_db, tlb)

    def adjust_limit(self, process_id: int, delta: int, pfn_db: PfnDatabase, tlb: TLB) -> List[Tuple[PageFrame, str]]:
        """Increment or decrement working set limit by delta."""
        return self.set_limit(process_id, self.limits[process_id] + delta, pfn_db, tlb)

    def get_active_frames(self, process_id: int, pfn_db: PfnDatabase) -> List[PageFrame]:
        """Return all active frames belonging to process_id."""
        return [f for f in pfn_db.frames if f.s == PfnState.ACTIVE and f.p == process_id]

    def trim_working_set(
        self,
        process_id: int,
        pfn_db: PfnDatabase,
        tlb: TLB
    ) -> List[Tuple[PageFrame, str]]:
        """
        Enforce working set quota.
        While active pages > quota, trim least recently used active page:
        - If dirty (d=1), moves to Modified list.
        - If clean (d=0), moves to Standby list.
        - Invalidate TLB entry.
        Returns list of (trimmed_frame, destination_list_name).
        """
        trimmed = []
        limit = self.limits[process_id]

        while True:
            active_frames = self.get_active_frames(process_id, pfn_db)
            if len(active_frames) <= limit:
                break

            # Find least recently used active frame (lowest timestamp u)
            victim = min(active_frames, key=lambda f: f.u)

            # Drop from TLB
            tlb.drop(victim.p, victim.pg)

            # Route to modified or standby list based on dirty bit
            if victim.d:
                target_state = PfnState.MODIFIED
                target_name = "modified"
            else:
                target_state = PfnState.STANDBY
                target_name = "standby"

            pfn_db.move_frame(victim, target_state)
            trimmed.append((victim, target_name))

        return trimmed

    def get_working_set_info(self, pfn_db: PfnDatabase) -> List[ProcessWorkingSetInfo]:
        """Generate summary info for all process working sets."""
        info = []
        for p in range(NUM_PROCESSES):
            active_frames = sorted(
                self.get_active_frames(p, pfn_db),
                key=lambda f: f.pg
            )
            info.append(ProcessWorkingSetInfo(
                process_id=p,
                process_name=PROCESS_NAMES[p],
                limit=self.limits[p],
                active_pages=[f.pg for f in active_frames],
                active_count=len(active_frames),
                color=PROCESS_COLORS[p]
            ))
        return info
