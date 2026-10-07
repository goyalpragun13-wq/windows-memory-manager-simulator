"""
Unit tests for the Windows VMM lifecycle:
Cache hits, Hard faults, Working set trimming, Soft faults, and Thrashing.
"""

from app.core.vmm import WindowsMemoryManager
from app.core.types import PageFaultType, PfnState


def test_initial_hard_fault_and_subsequent_hit():
    """Verify first access causes a Hard fault (disk read) and second causes a Cache Hit."""
    vmm = WindowsMemoryManager()

    # First access to P1:0 (read)
    fault1, frame1 = vmm.access_page(process_id=0, page_number=0, is_write=False)
    assert fault1 == PageFaultType.HARD
    assert vmm.stats.hard == 1
    assert vmm.stats.rd == 1
    assert vmm.stats.hit == 0
    assert frame1.s == PfnState.ACTIVE
    assert frame1.p == 0 and frame1.pg == 0

    # Second access to P1:0 (read)
    fault2, frame2 = vmm.access_page(process_id=0, page_number=0, is_write=False)
    assert fault2 == PageFaultType.HIT
    assert vmm.stats.hit == 1
    assert vmm.stats.hard == 1
    assert vmm.stats.rd == 1
    assert frame1.i == frame2.i


def test_working_set_trimming_and_soft_fault():
    """
    Verify working set trimming moves excess pages to Standby list,
    and subsequent access triggers a SOFT FAULT with zero disk reads.
    """
    vmm = WindowsMemoryManager()
    # Default limit for P1 is 4 pages.
    # Access pages 0, 1, 2, 3 (fills working set of 4 pages)
    for pg in range(4):
        vmm.access_page(0, pg, False)

    assert len(vmm.ws_manager.get_active_frames(0, vmm.pfn_db)) == 4
    assert len(vmm.pfn_db.lists[PfnState.STANDBY.value]) == 0

    # Access 5th page (page 4) -> triggers trimming of oldest active page (page 0)
    vmm.access_page(0, 4, False)

    # Process 1 active working set should still have exactly 4 pages
    assert len(vmm.ws_manager.get_active_frames(0, vmm.pfn_db)) == 4
    # Page 0 was clean, so it should now sit on the Standby list!
    assert len(vmm.pfn_db.lists[PfnState.STANDBY.value]) == 1
    trimmed_frame = vmm.pfn_db.get_frame(vmm.pfn_db.lists[PfnState.STANDBY.value][0])
    assert trimmed_frame.pg == 0

    disk_reads_before = vmm.stats.rd

    # Touch page 0 again -> must result in a SOFT FAULT!
    fault_rescue, rescued_frame = vmm.access_page(0, 0, False)
    assert fault_rescue == PageFaultType.SOFT
    assert vmm.stats.soft == 1
    # Disk reads MUST NOT increment on a soft fault!
    assert vmm.stats.rd == disk_reads_before
    assert rescued_frame.s == PfnState.ACTIVE
    assert len(vmm.pfn_db.lists[PfnState.STANDBY.value]) == 1  # another page got trimmed


def test_dirty_page_trimming_to_modified_list():
    """Dirty pages trimmed from working set must move to Modified list, not Standby."""
    vmm = WindowsMemoryManager()
    # Write to pages 0, 1, 2, 3
    for pg in range(4):
        vmm.access_page(0, pg, is_write=True)

    # Write to page 4 -> trims page 0
    vmm.access_page(0, 4, is_write=True)

    assert len(vmm.pfn_db.lists[PfnState.MODIFIED.value]) == 1
    mod_frame = vmm.pfn_db.get_frame(vmm.pfn_db.lists[PfnState.MODIFIED.value][0])
    assert mod_frame.pg == 0
    assert mod_frame.d == 1


def test_modified_page_writer_flush():
    """Modified page writer flushes modified list to standby and increments disk writes."""
    vmm = WindowsMemoryManager()
    for pg in range(5):
        vmm.access_page(0, pg, is_write=True)

    assert len(vmm.pfn_db.lists[PfnState.MODIFIED.value]) >= 1
    writes_before = vmm.stats.wr

    flushed = vmm.flush_modified_pages()
    assert flushed >= 1
    assert vmm.stats.wr == writes_before + flushed
    assert len(vmm.pfn_db.lists[PfnState.MODIFIED.value]) == 0
    assert len(vmm.pfn_db.lists[PfnState.STANDBY.value]) >= 1
