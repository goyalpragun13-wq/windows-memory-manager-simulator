"""
Unit tests for MMU, TLB, and virtual-to-physical address translation.
"""

from app.core.mmu import TLB, MMU
from app.core.types import PageFrame, PfnState


def test_virtual_address_decomposition():
    """Verify virtual address 0x2A3C correctly decomposes into VPN 2 and offset 0xA3C."""
    # 0x2A3C = (2 << 12) | 0xA3C = 8192 + 2620 = 10812
    va = 0x2A3C
    vpn, offset = MMU.decompose_address(va)
    assert vpn == 2
    assert offset == 0xA3C
    assert MMU.is_valid_virtual_address(va) is True


def test_physical_address_composition():
    """Verify PFN 7 and offset 0xA3C yields PA 0x7A3C."""
    pfn = 7
    offset = 0xA3C
    pa = MMU.compose_physical_address(pfn, offset)
    assert pa == 0x7A3C


def test_tlb_lookup_and_lru_replacement():
    """Verify TLB hit, miss, and LRU eviction after 4-entry capacity is exceeded."""
    tlb = TLB(capacity=4)

    # Misses for first 4 distinct pages
    assert tlb.lookup(0, 0) is False  # miss
    assert tlb.lookup(0, 1) is False  # miss
    assert tlb.lookup(0, 2) is False  # miss
    assert tlb.lookup(0, 3) is False  # miss
    assert tlb.misses == 4
    assert tlb.hits == 0

    # Hit for page 1
    assert tlb.lookup(0, 1) is True
    assert tlb.hits == 1

    # Adding 5th entry (0, 4) should evict oldest (which was 0, 0 since 0, 1 was refreshed)
    assert tlb.lookup(0, 4) is False
    assert len(tlb.entries) == 4
    assert tlb.contains(0, 0) is False  # 0,0 was evicted
    assert tlb.contains(0, 1) is True   # 0,1 still resident


def test_page_table_entry_states():
    """Verify page table reflects Valid, Transition Standby, Transition Modified, and Invalid."""
    tlb = TLB(4)
    frames = [
        PageFrame(i=0, s=PfnState.ACTIVE, p=0, pg=0, d=0, u=1),
        PageFrame(i=1, s=PfnState.STANDBY, p=0, pg=1, d=0, u=2),
        PageFrame(i=2, s=PfnState.MODIFIED, p=0, pg=2, d=1, u=3),
    ]

    ptes = MMU.get_page_table_entries(process_id=0, frames=frames, tlb=tlb)
    assert len(ptes) == 10

    # Page 0: Valid active
    assert ptes[0].valid is True
    assert ptes[0].frame_number == 0
    assert "Valid" in ptes[0].state_label

    # Page 1: Standby
    assert ptes[1].valid is False
    assert ptes[1].frame_number == 1
    assert "standby" in ptes[1].state_label.lower()

    # Page 2: Modified dirty
    assert ptes[2].valid is False
    assert ptes[2].frame_number == 2
    assert ptes[2].dirty is True
    assert "modified" in ptes[2].state_label.lower()

    # Page 3: Invalid (on disk)
    assert ptes[3].valid is False
    assert ptes[3].frame_number is None
    assert "Invalid" in ptes[3].state_label
