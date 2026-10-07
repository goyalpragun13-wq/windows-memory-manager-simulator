"""
Workload generation, benchmark traces, and educational scenarios.
"""

from typing import List, Dict, Any, Union


def generate_trace(workload_type: str, custom_string: str = "") -> List[int]:
    """
    Generate synthetic memory reference string traces.
    """
    if workload_type == "bel":
        return [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]

    elif workload_type == "loop":
        return [i % 10 for i in range(100)]

    elif workload_type == "loc":
        # Deterministic pseudo-random with 80/20 locality
        seed = 42
        trace = []
        def next_rand():
            nonlocal seed
            seed = (seed * 16807) % 2147483647
            return seed / 2147483647

        base = 0
        for _ in range(200):
            if next_rand() < 0.1:
                base = int(next_rand() * 8)
            if next_rand() < 0.85:
                trace.append(base + int(next_rand() * 4))
            else:
                trace.append(int(next_rand() * 16))
        return trace

    elif workload_type == "rnd":
        seed = 42
        trace = []
        def next_rand():
            nonlocal seed
            seed = (seed * 16807) % 2147483647
            return seed / 2147483647
        for _ in range(200):
            trace.append(int(next_rand() * 16))
        return trace

    elif workload_type == "cus":
        cleaned = custom_string.replace(",", " ").split()
        res = []
        for token in cleaned:
            try:
                res.append(int(token))
            except ValueError:
                pass
        return res

    return []


# Scenario Step Definition: either a page access [process, page, is_write] or a command ['flush'] or ['kill', process]
ScenarioStep = Union[List[Union[int, str]], Dict[str, Any]]

SCENARIO_CONFIGS = [
    {
        "id": 1,
        "name": "Good Locality",
        "description": "Processes exhibit high temporal and spatial locality within their working sets.",
        "working_set_limits": [4, 4, 3],
        "expected_counters": {"hit": 28, "soft": 0, "hard": 8, "wr": 0},
    },
    {
        "id": 2,
        "name": "Thrashing",
        "description": "Working set limits restricted to 1 page each, inducing severe thrashing.",
        "working_set_limits": [1, 1, 1],
        "expected_counters": {"hit": 0, "soft": 0, "hard": 60, "wr": 0},
    },
    {
        "id": 3,
        "name": "Sequential Scan",
        "description": "Process scans through virtual pages sequentially, exercising standby reclamation.",
        "working_set_limits": [4, 4, 3],
        "expected_counters": {"hit": 0, "soft": 20, "hard": 10, "wr": 0},
    },
    {
        "id": 4,
        "name": "Memory Pressure",
        "description": "High quota allocation across all processes rapidly exhausts physical frames.",
        "working_set_limits": [8, 8, 8],
        "expected_counters": {"hit": 0, "soft": 0, "hard": 48, "wr": 0},
    },
    {
        "id": 5,
        "name": "Write-Heavy",
        "description": "Extensive dirty page generation followed by modified page writer flush.",
        "working_set_limits": [4, 4, 3],
        "expected_counters": {"hit": 0, "soft": 10, "hard": 10, "wr": 6},
    },
    {
        "id": 6,
        "name": "Process Exit",
        "description": "Process termination triggers bulk frame reclamation back to the Free list.",
        "working_set_limits": [4, 4, 3],
        "expected_counters": {"hit": 0, "soft": 0, "hard": 12, "wr": 0},
    },
]


def build_scenario_steps(scenario_id: int) -> List[Any]:
    """Build the exact instruction sequence for a given scenario."""
    if scenario_id == 1:
        steps = []
        def push_pair(p, pg):
            steps.append([p, pg, 0])
            steps.append([p, pg, 0])
        for r in range(6):
            push_pair(0, [0, 1, 2][r % 3])
            push_pair(1, [3, 4, 5][r % 3])
            push_pair(2, [6, 7][r % 2])
        return steps

    elif scenario_id == 2:
        return [[i % 3, (i // 3) % 10, 0] for i in range(60)]

    elif scenario_id == 3:
        return [[0, i % 10, 0] for i in range(30)]

    elif scenario_id == 4:
        steps = []
        for _ in range(2):
            for r in range(8):
                for p in range(3):
                    steps.append([p, r, 0])
        return steps

    elif scenario_id == 5:
        steps = []
        for i in range(10):
            steps.append([0, i, 1])
        steps.append(["flush"])
        for i in range(10):
            steps.append([0, i, 0])
        return steps

    elif scenario_id == 6:
        steps = []
        for i in range(4):
            steps.append([0, i, 0])
            steps.append([1, i, 0])
        steps.append(["kill", 0])
        for i in range(4):
            steps.append([2, i, 0])
        return steps

    return []
