"""
Hardware MMU (Memory Management Unit) and TLB (Translation Lookaside Buffer) simulation.
"""

from typing import List, Optional, Tuple
from app.config import TLB_CAPACITY, PAGE_OFFSET_BITS, OFFSET_MASK, PAGES_PER_PROCESS, PAGE_SIZE
from app.core.types import PageFrame, PfnState, PageFaultType, AddressTranslationResult, PageTableEntry


class TLB:
    """
    Simulates a 4-entry Translation Lookaside Buffer with LRU replacement.
    Stores tagged keys as (process_id * 100 + page_number).
    """

    def __init__(self, capacity: int = TLB_CAPACITY):
        self.capacity = capacity
        self.entries: List[int] = []  # List of encoded keys (LRU at index 0, MRU at end)
        self.hits: int = 0
        self.misses: int = 0

    def reset(self) -> None:
        """Clear all entries and telemetry."""
        self.entries.clear()
        self.hits = 0
        self.misses = 0

    def lookup(self, process_id: int, page_number: int) -> bool:
        """
        Check if (process_id, page_number) is resident in the TLB.
        Updates LRU position and hit/miss statistics.
        """
        key = process_id * 100 + page_number
        if key in self.entries:
            self.hits += 1
            self.entries.remove(key)
            self.entries.append(key)
            return True
        else:
            self.misses += 1
            if len(self.entries) >= self.capacity:
                self.entries.pop(0)
            self.entries.append(key)
            return False

    def contains(self, process_id: int, page_number: int) -> bool:
        """Check if entry exists without updating LRU order or stats."""
        return (process_id * 100 + page_number) in self.entries

    def drop(self, process_id: int, page_number: int) -> None:
        """Invalidate a specific TLB entry (e.g. during page trimming)."""
        key = process_id * 100 + page_number
        if key in self.entries:
            self.entries.remove(key)

    def flush_process(self, process_id: int) -> None:
        """Invalidate all TLB entries for a specific process (e.g. on process exit)."""
        self.entries = [k for k in self.entries if (k // 100) != process_id]


class MMU:
    """
    Simulates the processor MMU for virtual address decomposition and translation.
    """

    def __init__(self, tlb: Optional[TLB] = None):
        self.tlb = tlb or TLB()

    @staticmethod
    def decompose_address(virtual_address: int) -> Tuple[int, int]:
        """
        Split virtual address into (VPN, offset).
        VPN = virtual_address >> 12
        Offset = virtual_address & 0xFFF
        """
        vpn = (virtual_address >> PAGE_OFFSET_BITS)
        offset = virtual_address & OFFSET_MASK
        return vpn, offset

    @staticmethod
    def compose_physical_address(frame_number: int, offset: int) -> int:
        """
        Compute 32-bit physical address from Physical Frame Number (PFN) and byte offset.
        """
        return (frame_number << PAGE_OFFSET_BITS) | offset

    @staticmethod
    def is_valid_virtual_address(virtual_address: int) -> bool:
        """Validate that address falls within simulated address space 0x0000 - 0x9FFF."""
        max_addr = (PAGES_PER_PROCESS * PAGE_SIZE) - 1
        return 0 <= virtual_address <= max_addr

    @staticmethod
    def get_page_table_entries(
        process_id: int,
        frames: List[PageFrame],
        tlb: TLB
    ) -> List[PageTableEntry]:
        """
        Construct the architectural Page Table for the given process.
        """
        entries = []
        for page_num in range(PAGES_PER_PROCESS):
            frame = next(
                (f for f in frames if f.p == process_id and f.pg == page_num and f.s not in (PfnState.FREE, PfnState.ZEROED)),
                None
            )
            if frame is None:
                state_label = "Invalid (on disk)"
                valid = False
                frame_id = None
                dirty = False
            elif frame.s == PfnState.ACTIVE:
                state_label = "Valid (active)"
                valid = True
                frame_id = frame.i
                dirty = bool(frame.d)
            elif frame.s == PfnState.STANDBY:
                state_label = "Transition (standby)"
                valid = False
                frame_id = frame.i
                dirty = False
            elif frame.s == PfnState.MODIFIED:
                state_label = "Transition (modified)"
                valid = False
                frame_id = frame.i
                dirty = bool(frame.d)
            else:
                state_label = "Invalid"
                valid = False
                frame_id = None
                dirty = False

            entries.append(PageTableEntry(
                page_number=page_num,
                state_label=state_label,
                valid=valid,
                frame_number=frame_id,
                dirty=dirty,
                in_tlb=tlb.contains(process_id, page_num)
            ))
        return entries
