"""
Unit tests for the Windows Page Frame Number (PFN) Database.
"""

from app.core.pfn_database import PfnDatabase
from app.core.types import PfnState


def test_pfn_initial_state():
    """Verify fresh PFN database boots with all 16 frames in Free list."""
    db = PfnDatabase(16)
    assert len(db.frames) == 16
    assert len(db.lists[PfnState.FREE.value]) == 16
    assert len(db.lists[PfnState.ZEROED.value]) == 0
    assert len(db.lists[PfnState.STANDBY.value]) == 0
    assert len(db.lists[PfnState.MODIFIED.value]) == 0
    assert all(f.s == PfnState.FREE for f in db.frames)


def test_zero_page_thread_conversion():
    """Verify background zero-page thread converts free frame to zeroed."""
    db = PfnDatabase(16)
    converted_id = db.step_zero_page_thread()
    assert converted_id == 0
    assert db.get_frame(0).s == PfnState.ZEROED
    assert len(db.lists[PfnState.ZEROED.value]) == 1
    assert len(db.lists[PfnState.FREE.value]) == 15


def test_allocation_priority_zeroed_over_free():
    """Allocation must prioritize zeroed frames before free frames."""
    db = PfnDatabase(16)
    # Convert one frame to zeroed
    db.step_zero_page_thread()

    frame, source = db.take_frame_for_allocation()
    assert source == "zeroed"
    assert frame.i == 0
    db.move_frame(frame, PfnState.ACTIVE)

    frame2, source2 = db.take_frame_for_allocation()
    assert source2 == "free"
    assert frame2.i == 1


def test_flush_modified_pages_to_standby():
    """Modified page writer must write dirty pages to pagefile and transition to standby."""
    db = PfnDatabase(16)
    frame = db.get_frame(2)
    db.move_frame(frame, PfnState.MODIFIED)
    frame.d = 1
    frame.p = 0
    frame.pg = 5

    assert frame.i in db.lists[PfnState.MODIFIED.value]

    count, flushed = db.flush_modified_pages()
    assert count == 1
    assert flushed == [2]
    assert frame.s == PfnState.STANDBY
    assert frame.d == 0  # Dirty bit cleared
    assert frame.i in db.lists[PfnState.STANDBY.value]
    assert len(db.lists[PfnState.MODIFIED.value]) == 0


def test_reclaim_process_frames_on_exit():
    """Terminating a process must reclaim all its active/standby/modified frames to Free list."""
    db = PfnDatabase(16)
    # Assign frame 3 to process 1 as active
    f3 = db.get_frame(3)
    db.move_frame(f3, PfnState.ACTIVE)
    f3.p = 1
    f3.pg = 2

    # Assign frame 4 to process 1 as standby
    f4 = db.get_frame(4)
    db.move_frame(f4, PfnState.STANDBY)
    f4.p = 1
    f4.pg = 3

    reclaimed = db.reclaim_process_frames(1)
    assert reclaimed == 2
    assert f3.s == PfnState.FREE
    assert f4.s == PfnState.FREE
    assert f3.p == -1 and f4.p == -1
    assert f3.i in db.lists[PfnState.FREE.value]
    assert f4.i in db.lists[PfnState.FREE.value]
