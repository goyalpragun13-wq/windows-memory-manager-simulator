"""
Windows Page Frame Number (PFN) Database implementation.
Manages the global physical frames and their transitions between system lists.
"""

from typing import List, Dict, Optional, Tuple
from app.config import NUM_FRAMES
from app.core.types import PfnState, PageFrame


class PfnDatabase:
    """
    Simulates the Windows NT / 10 / 11 Page Frame Number (PFN) Database.
    Tracks state, owner, virtual page, dirty flag, and list linkage for each frame.
    """

    def __init__(self, num_frames: int = NUM_FRAMES):
        self.num_frames = num_frames
        self.frames: List[PageFrame] = []
        self.lists: Dict[str, List[int]] = {
            PfnState.FREE.value: [],
            PfnState.ZEROED.value: [],
            PfnState.STANDBY.value: [],
            PfnState.MODIFIED.value: [],
        }
        self.reset()

    def reset(self) -> None:
        """Reset all physical frames to the Free list."""
        self.frames = [
            PageFrame(i=i, s=PfnState.FREE, p=-1, pg=-1, d=0, u=0)
            for i in range(self.num_frames)
        ]
        self.lists = {
            PfnState.FREE.value: list(range(self.num_frames)),
            PfnState.ZEROED.value: [],
            PfnState.STANDBY.value: [],
            PfnState.MODIFIED.value: [],
        }

    def get_frame(self, frame_index: int) -> PageFrame:
        """Retrieve a PageFrame by its physical index."""
        return self.frames[frame_index]

    def find_process_page(self, process_id: int, page_number: int) -> Optional[PageFrame]:
        """
        Locate any frame holding (process_id, page_number) that is not Free or Zeroed.
        """
        for frame in self.frames:
            if (
                frame.p == process_id
                and frame.pg == page_number
                and frame.s not in (PfnState.FREE, PfnState.ZEROED)
            ):
                return frame
        return None

    def move_frame(self, frame: PageFrame, new_state: PfnState) -> None:
        """
        Transition a physical frame to a new state and update list memberships.
        """
        old_state_str = frame.s.value
        new_state_str = new_state.value

        # Remove from current list if present
        if old_state_str in self.lists and frame.i in self.lists[old_state_str]:
            self.lists[old_state_str].remove(frame.i)

        frame.s = new_state

        # Append to new list if not active (active frames are in process working sets)
        if new_state != PfnState.ACTIVE:
            if new_state_str in self.lists and frame.i not in self.lists[new_state_str]:
                self.lists[new_state_str].append(frame.i)

    def step_zero_page_thread(self) -> Optional[int]:
        """
        Simulate the idle-priority zero-page thread.
        Picks the first free frame and converts it to a zeroed frame.
        """
        if self.lists[PfnState.FREE.value]:
            frame_id = self.lists[PfnState.FREE.value][0]
            frame = self.frames[frame_id]
            self.move_frame(frame, PfnState.ZEROED)
            frame.p = -1
            frame.pg = -1
            frame.d = 0
            return frame_id
        return None

    def flush_modified_pages(self) -> Tuple[int, List[int]]:
        """
        Simulate the Modified Page Writer.
        Flushes all pages on the modified list to disk and moves them to standby.
        Returns (number_of_flushed_pages, list_of_frame_ids).
        """
        mod_frames = list(self.lists[PfnState.MODIFIED.value])
        for frame_id in mod_frames:
            frame = self.frames[frame_id]
            frame.d = 0
            self.move_frame(frame, PfnState.STANDBY)
        return len(mod_frames), mod_frames

    def take_frame_for_allocation(self) -> Tuple[PageFrame, str]:
        """
        Select an available physical frame according to Windows PFN allocation priority:
        1. Zeroed list
        2. Free list
        3. (If neither, flush modified pages if standby empty)
        4. Standby list (oldest standby page reclaimed; data lost to virtual owner)
        5. Active frames (steals least recently used active frame across system)
        """
        # 1. Zeroed list
        if self.lists[PfnState.ZEROED.value]:
            frame_id = self.lists[PfnState.ZEROED.value][0]
            return self.frames[frame_id], "zeroed"

        # 2. Free list
        if self.lists[PfnState.FREE.value]:
            frame_id = self.lists[PfnState.FREE.value][0]
            return self.frames[frame_id], "free"

        # 3. If standby is empty and modified has pages, auto-flush
        if not self.lists[PfnState.STANDBY.value] and self.lists[PfnState.MODIFIED.value]:
            self.flush_modified_pages()

        # 4. Standby list
        if self.lists[PfnState.STANDBY.value]:
            frame_id = self.lists[PfnState.STANDBY.value][0]
            return self.frames[frame_id], "standby"

        # 5. Steal oldest active frame
        active_frames = [f for f in self.frames if f.s == PfnState.ACTIVE]
        if active_frames:
            oldest_frame = min(active_frames, key=lambda f: f.u)
            return oldest_frame, "stolen"

        # Fallback (should not occur with 16 frames)
        return self.frames[0], "fallback"

    def reclaim_process_frames(self, process_id: int) -> int:
        """
        Reclaim all frames owned by a terminating process, returning them to the Free list.
        """
        count = 0
        for frame in self.frames:
            if frame.p == process_id and frame.s not in (PfnState.FREE, PfnState.ZEROED):
                frame.p = -1
                frame.pg = -1
                frame.d = 0
                self.move_frame(frame, PfnState.FREE)
                count += 1
        return count
