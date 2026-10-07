"""
Page replacement algorithms and Belady's anomaly detection for the experiment lab.
Implements FIFO, LRU, Clock (Second Chance), and Optimal (Belady MIN).
"""

from typing import List, Dict, Any, Tuple


def simulate_algorithm(policy: str, trace: List[int], num_frames: int) -> int:
    """
    Simulate page replacement algorithm for a given reference string and frame capacity.
    Returns total number of page faults.
    """
    if not trace or num_frames <= 0:
        return 0

    frames: List[int] = []
    ref_bits: List[int] = []
    clock_hand: int = 0
    faults: int = 0

    for i, page in enumerate(trace):
        if page in frames:
            idx = frames.index(page)
            if policy == "LRU":
                # Move to MRU position (end of list)
                frames.pop(idx)
                frames.append(page)
            elif policy == "Clock":
                ref_bits[idx] = 1
            continue

        # Page Fault
        faults += 1

        if len(frames) < num_frames:
            frames.append(page)
            if policy == "Clock":
                ref_bits.append(1)
            continue

        # Eviction required
        if policy in ("FIFO", "LRU"):
            frames.pop(0)
            frames.append(page)
        elif policy == "Clock":
            while ref_bits[clock_hand] == 1:
                ref_bits[clock_hand] = 0
                clock_hand = (clock_hand + 1) % num_frames
            frames[clock_hand] = page
            ref_bits[clock_hand] = 1
            clock_hand = (clock_hand + 1) % num_frames
        elif policy == "OPT":
            # Evict frame whose next occurrence is furthest in future (or never)
            victim_idx = 0
            furthest_next = -1
            for m, resident_page in enumerate(frames):
                try:
                    next_idx = trace.index(resident_page, i + 1)
                except ValueError:
                    next_idx = 10**9  # Never used again
                if next_idx > furthest_next:
                    furthest_next = next_idx
                    victim_idx = m
            frames[victim_idx] = page

    return faults


def run_experiment_lab(
    trace: List[int],
    frame_range: List[int] = None
) -> Dict[str, Any]:
    """
    Run FIFO, LRU, Clock, and OPT across a sweep of physical frame sizes.
    Detects Belady's Anomaly if present.
    """
    if frame_range is None:
        frame_range = list(range(1, 11))

    policies = ["FIFO", "LRU", "Clock", "OPT"]
    results: Dict[str, List[int]] = {p: [] for p in policies}

    for policy in policies:
        for f in frame_range:
            results[policy].append(simulate_algorithm(policy, trace, f))

    # Detect Belady's Anomaly in FIFO
    anomalies: List[Dict[str, int]] = []
    fifo_results = results["FIFO"]
    for idx in range(len(frame_range) - 1):
        f_current = frame_range[idx]
        f_next = frame_range[idx + 1]
        faults_curr = fifo_results[idx]
        faults_next = fifo_results[idx + 1]
        if faults_next > faults_curr:
            anomalies.append({
                "from_frames": f_current,
                "to_frames": f_next,
                "faults_before": faults_curr,
                "faults_after": faults_next,
            })

    return {
        "trace_length": len(trace),
        "frame_range": frame_range,
        "results": results,
        "belady_anomalies": anomalies,
    }


def replay_global_baseline(
    trace: List[Tuple[int, int, int]],
    total_frames: int = 16
) -> Dict[str, Dict[str, int]]:
    """
    Replay a multi-process trace [(process, page, is_write)] on a single global pool
    without working sets or standby/modified caching (classic textbook FIFO & LRU).
    Returns disk reads (faults) and disk writes.
    """
    def run_baseline(policy: str) -> Dict[str, int]:
        resident: List[int] = []
        dirty_map: Dict[int, bool] = {}
        faults = 0
        writes = 0

        for p, pg, w in trace:
            key = p * 100 + pg
            if key in resident:
                if policy == "LRU":
                    resident.remove(key)
                    resident.append(key)
            else:
                faults += 1
                if len(resident) >= total_frames:
                    victim = resident.pop(0)
                    if dirty_map.get(victim, False):
                        writes += 1
                        dirty_map.pop(victim, None)
                resident.append(key)

            if w:
                dirty_map[key] = True

        return {"reads": faults, "writes": writes}

    return {
        "FIFO": run_baseline("FIFO"),
        "LRU": run_baseline("LRU")
    }
