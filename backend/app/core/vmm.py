"""
Master Windows Virtual Memory Manager (VMM) kernel simulation.
Orchestrates PFN Database, MMU, TLB, Working Sets, and paging workflows.
"""

from typing import List, Tuple, Optional, Dict, Any
from app.config import (
    NUM_FRAMES,
    NUM_PROCESSES,
    PAGES_PER_PROCESS,
    MAX_LOG_ENTRIES,
    MAX_HISTORY_ENTRIES,
)
from app.core.types import (
    PfnState,
    PageFaultType,
    PageFrame,
    VmmStatistics,
    VmmStateSnapshot,
    AddressTranslationResult,
)
from app.core.pfn_database import PfnDatabase
from app.core.mmu import TLB, MMU
from app.core.working_set import WorkingSetManager


class WindowsMemoryManager:
    """
    Simulates the Windows Virtual Memory Manager subsystem.
    """

    def __init__(self):
        self.pfn_db = PfnDatabase(NUM_FRAMES)
        self.tlb = TLB()
        self.mmu = MMU(self.tlb)
        self.ws_manager = WorkingSetManager()

        self.clock: int = 0
        self.trace: List[Tuple[int, int, int]] = []  # [(process_id, page_number, is_write)]
        self.log: List[str] = []
        self.history: List[List[int]] = []          # [[hit, soft, hard], ...]

        self.stats = VmmStatistics()
        self.current_process: int = 0
        self.write_mode: bool = False

        # Hot working set pages for stochastic auto-workload simulation
        self.hot_pages = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
        self.reset()

    def reset(self, limits: Optional[List[int]] = None) -> None:
        """Reset simulator state to fresh boot condition."""
        self.pfn_db.reset()
        self.tlb.reset()
        if limits:
            self.ws_manager.limits = list(limits)
        else:
            self.ws_manager.reset()

        self.clock = 0
        self.trace.clear()
        self.log.clear()
        self.history.clear()
        self.stats = VmmStatistics()
        self.current_process = 0
        self.write_mode = False
        self.hot_pages = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
        self._add_log("Windows Memory Manager booted. Physical memory: 16 frames.")

    def _add_log(self, message: str) -> None:
        """Add kernel event to circular log buffer."""
        self.log.insert(0, message)
        if len(self.log) > MAX_LOG_ENTRIES:
            self.log.pop()

    def access_page(
        self,
        process_id: int,
        page_number: int,
        is_write: bool = False
    ) -> Tuple[PageFaultType, PageFrame]:
        """
        Execute virtual memory access request.
        Handles TLB lookup, hit/soft-fault/hard-fault resolution, working set trimming,
        and background zero-page thread maintenance.
        """
        self.clock += 1
        self.trace.append((process_id, page_number, 1 if is_write else 0))

        # TLB query
        tlb_hit = self.tlb.lookup(process_id, page_number)
        if tlb_hit:
            self.stats.tlb_hits += 1
        else:
            self.stats.tlb_misses += 1

        # Check if page currently resides anywhere in physical RAM
        existing_frame = self.pfn_db.find_process_page(process_id, page_number)

        fault_type: PageFaultType
        target_frame: PageFrame

        if existing_frame and existing_frame.s == PfnState.ACTIVE:
            # --- CACHE HIT (Page is in process working set) ---
            fault_type = PageFaultType.HIT
            self.stats.hit += 1
            op = "write" if is_write else "read"
            self._add_log(f"HIT P{process_id + 1}:{page_number} ({op})")
            target_frame = existing_frame

        elif existing_frame:
            # --- SOFT FAULT (Page is cached on Standby or Modified list) ---
            fault_type = PageFaultType.SOFT
            self.stats.soft += 1
            from_state = existing_frame.s.value
            self.pfn_db.move_frame(existing_frame, PfnState.ACTIVE)
            self._add_log(
                f"SOFT fault P{process_id + 1}:{page_number}: reattached from {from_state} list, zero disk I/O"
            )
            target_frame = existing_frame

        else:
            # --- HARD FAULT (Page must be read from disk/pagefile) ---
            fault_type = PageFaultType.HARD
            self.stats.hard += 1
            self.stats.rd += 1

            frame, source = self.pfn_db.take_frame_for_allocation()

            # If stealing a frame or reclaiming standby, drop victim TLB and handle dirty writes
            if source == "standby":
                self._add_log(
                    f"Reclaimed oldest standby frame #{frame.i} (P{frame.p + 1}:{frame.pg} evicted from memory)"
                )
            elif source == "stolen":
                self.tlb.drop(frame.p, frame.pg)
                if frame.d:
                    self.stats.wr += 1
                self._add_log(
                    f"Frame pool exhausted: stole frame #{frame.i} from P{frame.p + 1}:{frame.pg}"
                )

            self.pfn_db.move_frame(frame, PfnState.ACTIVE)
            frame.p = process_id
            frame.pg = page_number
            frame.d = 0
            self._add_log(
                f"HARD fault P{process_id + 1}:{page_number}: read from disk into frame #{frame.i}"
            )
            target_frame = frame

        # Update dirty bit and usage timestamp
        if is_write:
            target_frame.d = 1
        target_frame.u = self.clock

        # Enforce Working Set Limit (Working Set Trimming)
        trimmed = self.ws_manager.trim_working_set(process_id, self.pfn_db, self.tlb)
        for victim, dest in trimmed:
            self._add_log(
                f"Trimmed P{process_id + 1}:{victim.pg} from working set to {dest} list"
            )

        # Idle-priority Zero Page Thread maintenance
        self.pfn_db.step_zero_page_thread()

        # Update telemetry
        self._update_telemetry()

        return fault_type, target_frame

    def flush_modified_pages(self) -> int:
        """
        Modified Page Writer worker: flushes all dirty modified frames to pagefile,
        clears dirty flags, and moves frames to Standby list.
        """
        count, flushed = self.pfn_db.flush_modified_pages()
        if count > 0:
            self.stats.wr += count
            self._add_log(
                f"Modified page writer: {count} dirty page(s) written to pagefile, moved to standby"
            )
        self._update_telemetry()
        return count

    def terminate_process(self, process_id: int) -> int:
        """
        Process termination: invalidates process TLB entries and returns all
        associated physical frames to the Free list.
        """
        self.tlb.flush_process(process_id)
        count = self.pfn_db.reclaim_process_frames(process_id)
        self._add_log(
            f"Process P{process_id + 1} terminated: {count} frames reclaimed to Free list"
        )
        self._update_telemetry()
        return count

    def set_working_set_limit(self, process_id: int, limit: int) -> None:
        """Adjust process working set limit and execute immediate trimming if needed."""
        trimmed = self.ws_manager.set_limit(process_id, limit, self.pfn_db, self.tlb)
        for victim, dest in trimmed:
            self._add_log(
                f"Trimmed P{process_id + 1}:{victim.pg} after quota change to {dest} list"
            )
        self._update_telemetry()

    def translate_and_access(
        self,
        virtual_address: int,
        process_id: Optional[int] = None,
        is_write: Optional[bool] = None
    ) -> AddressTranslationResult:
        """
        Perform MMU address decomposition, TLB lookup, simulated memory access,
        and calculate physical byte address.
        """
        if process_id is None:
            process_id = self.current_process
        if is_write is None:
            is_write = self.write_mode

        if not self.mmu.is_valid_virtual_address(virtual_address):
            return AddressTranslationResult(
                virtual_address=virtual_address,
                virtual_address_hex=f"0x{virtual_address:04X}",
                page_number=-1,
                offset=-1,
                offset_hex="0x0",
                tlb_hit=False,
                fault_type=PageFaultType.HARD,
                message=f"Invalid virtual address: 0x{virtual_address:04X} exceeds 0x9FFF."
            )

        vpn, offset = self.mmu.decompose_address(virtual_address)
        had_tlb_hit = self.tlb.contains(process_id, vpn)

        fault_type, frame = self.access_page(process_id, vpn, is_write)
        phys_addr = self.mmu.compose_physical_address(frame.i, offset)

        status_msg = (
            f"VA 0x{virtual_address:04X} -> VPN {vpn}, Offset 0x{offset:03X}. "
            f"TLB {'HIT' if had_tlb_hit else 'MISS'}, {fault_type.value.upper()} FAULT. "
            f"Frame #{frame.i} => PA 0x{phys_addr:05X}."
        )

        return AddressTranslationResult(
            virtual_address=virtual_address,
            virtual_address_hex=f"0x{virtual_address:04X}",
            page_number=vpn,
            offset=offset,
            offset_hex=f"0x{offset:03X}",
            tlb_hit=had_tlb_hit,
            fault_type=fault_type,
            frame_number=frame.i,
            physical_address=phys_addr,
            physical_address_hex=f"0x{phys_addr:05X}",
            message=status_msg
        )

    def is_thrashing(self) -> bool:
        """
        Detect thrashing condition:
        Memory pool is exhausted (Free and Zero lists empty) and >= 10 of last 20 accesses
        required hard page faults.
        """
        if len(self.history) < 20:
            return False
        recent = self.history[-20:]
        hard_delta = recent[-1][2] - recent[0][2]
        no_free = len(self.pfn_db.lists[PfnState.FREE.value]) == 0
        no_zero = len(self.pfn_db.lists[PfnState.ZEROED.value]) == 0
        return hard_delta >= 10 and no_free and no_zero

    def _update_telemetry(self) -> None:
        """Recalculate running statistical ratios and record history point."""
        total = self.stats.hit + self.stats.soft + self.stats.hard
        self.stats.accesses = total
        if total > 0:
            self.stats.fault_rate_pct = round(((self.stats.soft + self.stats.hard) / total) * 100.0, 1)
            self.stats.soft_fault_ratio_pct = round((self.stats.soft / total) * 100.0, 1)

        tlb_total = self.stats.tlb_hits + self.stats.tlb_misses
        if tlb_total > 0:
            self.stats.tlb_hit_rate_pct = round((self.stats.tlb_hits / tlb_total) * 100.0, 1)

        self.history.append([self.stats.hit, self.stats.soft, self.stats.hard])
        if len(self.history) > MAX_HISTORY_ENTRIES:
            self.history.pop(0)

    def get_snapshot(self) -> VmmStateSnapshot:
        """Generate complete state snapshot for UI / API consumption."""
        return VmmStateSnapshot(
            timestamp=self.clock,
            frames=[f.model_copy() for f in self.pfn_db.frames],
            lists={k: list(v) for k, v in self.pfn_db.lists.items()},
            working_sets=self.ws_manager.get_working_set_info(self.pfn_db),
            stats=self.stats.model_copy(),
            log=list(self.log),
            tlb=list(self.tlb.entries),
            history=[list(h) for h in self.history],
            current_process=self.current_process,
            write_mode=self.write_mode,
            is_thrashing=self.is_thrashing(),
        )
