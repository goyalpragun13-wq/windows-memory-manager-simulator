"""
Unit tests for page replacement algorithms (FIFO, LRU, Clock, OPT) and Belady's Anomaly.
"""

from app.core.algorithms import simulate_algorithm, run_experiment_lab
from app.core.workloads import generate_trace


def test_belady_string_known_results():
    """
    Validate textbook Belady string 1,2,3,4,1,2,5,1,2,3,4,5 across 3 and 4 frames.
    Known results:
      FIFO 3 frames = 9 faults
      FIFO 4 frames = 10 faults (Belady's Anomaly!)
      LRU 3 frames = 10 faults
      LRU 4 frames = 8 faults
      OPT 3 frames = 7 faults
      OPT 4 frames = 6 faults
    """
    trace = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]

    assert simulate_algorithm("FIFO", trace, 3) == 9
    assert simulate_algorithm("FIFO", trace, 4) == 10
    assert simulate_algorithm("LRU", trace, 3) == 10
    assert simulate_algorithm("LRU", trace, 4) == 8
    assert simulate_algorithm("OPT", trace, 3) == 7
    assert simulate_algorithm("OPT", trace, 4) == 6


def test_belady_anomaly_detection():
    """Verify experiment lab automatically detects Belady's Anomaly on the Belady string."""
    trace = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    lab = run_experiment_lab(trace, frame_range=[3, 4])

    assert len(lab["belady_anomalies"]) == 1
    anom = lab["belady_anomalies"][0]
    assert anom["from_frames"] == 3
    assert anom["to_frames"] == 4
    assert anom["faults_before"] == 9
    assert anom["faults_after"] == 10


def test_optimal_minimality():
    """Verify OPT produces fewer or equal page faults than FIFO, LRU, and Clock on locality trace."""
    trace = generate_trace("loc")
    for f in [2, 3, 4, 5, 6]:
        opt_faults = simulate_algorithm("OPT", trace, f)
        fifo_faults = simulate_algorithm("FIFO", trace, f)
        lru_faults = simulate_algorithm("LRU", trace, f)
        clock_faults = simulate_algorithm("Clock", trace, f)

        assert opt_faults <= fifo_faults
        assert opt_faults <= lru_faults
        assert opt_faults <= clock_faults
