"""
Verification test runner service for validating simulator correctness.
"""

from typing import List, Dict, Any
from pydantic import BaseModel
from app.core.algorithms import simulate_algorithm
from app.core.workloads import generate_trace, SCENARIO_CONFIGS, build_scenario_steps
from app.core.vmm import WindowsMemoryManager
from app.core.types import PfnState


class TestResultItem(BaseModel):
    name: str
    expected: str
    actual: str
    passed: bool


class TestSuiteReport(BaseModel):
    total_tests: int
    passed_tests: int
    failed_tests: int
    success_rate_pct: float
    results: List[TestResultItem]


class SimulationTestRunner:
    """Runs automated verification tests against known academic standards."""

    @staticmethod
    def run_all() -> TestSuiteReport:
        items: List[TestResultItem] = []
        belady_trace = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]

        # 1. Classical Belady String benchmarks
        benchmark_checks = [
            ("FIFO", 3, 9),
            ("FIFO", 4, 10),  # Belady's Anomaly!
            ("LRU", 3, 10),
            ("LRU", 4, 8),
            ("OPT", 3, 7),
            ("OPT", 4, 6),
        ]

        for policy, frames, expected in benchmark_checks:
            actual = simulate_algorithm(policy, belady_trace, frames)
            items.append(TestResultItem(
                name=f"{policy} on Belady String ({frames} frames)",
                expected=f"{expected} faults",
                actual=f"{actual} faults",
                passed=(actual == expected)
            ))

        # 2. Optimal Algorithm Invariance Check
        locality_trace = generate_trace("loc")
        opt_f4 = simulate_algorithm("OPT", locality_trace, 4)
        fifo_f4 = simulate_algorithm("FIFO", locality_trace, 4)
        lru_f4 = simulate_algorithm("LRU", locality_trace, 4)
        clock_f4 = simulate_algorithm("Clock", locality_trace, 4)
        opt_is_minimal = (opt_f4 <= min(fifo_f4, lru_f4, clock_f4))

        items.append(TestResultItem(
            name="OPT Minimality Invariant (OPT <= FIFO, LRU, Clock @ 4 frames)",
            expected="True",
            actual=str(opt_is_minimal),
            passed=opt_is_minimal
        ))

        # 3. Scenario Executions & Invariant Validations
        vmm = WindowsMemoryManager()

        for config in SCENARIO_CONFIGS:
            s_id = config["id"]
            name = config["name"]
            expected_counts = config["expected_counters"]

            vmm.reset(limits=config["working_set_limits"])
            steps = build_scenario_steps(s_id)

            for step in steps:
                if step[0] == "kill":
                    vmm.terminate_process(step[1])
                elif step[0] == "flush":
                    vmm.flush_modified_pages()
                else:
                    vmm.access_page(step[0], step[1], bool(step[2]))

            # Validate Counters
            act_counters = {
                "hit": vmm.stats.hit,
                "soft": vmm.stats.soft,
                "hard": vmm.stats.hard,
                "wr": vmm.stats.wr,
            }
            counters_match = (act_counters == expected_counts)
            exp_str = f"H:{expected_counts['hit']}/S:{expected_counts['soft']}/HD:{expected_counts['hard']}/W:{expected_counts['wr']}"
            act_str = f"H:{act_counters['hit']}/S:{act_counters['soft']}/HD:{act_counters['hard']}/W:{act_counters['wr']}"

            items.append(TestResultItem(
                name=f"Scenario {s_id} ({name}) Counter Verification",
                expected=exp_str,
                actual=act_str,
                passed=counters_match
            ))

            # Validate Conservation of Physical Frames (Must equal 16)
            active_count = len([f for f in vmm.pfn_db.frames if f.s == PfnState.ACTIVE])
            list_counts = sum(len(v) for v in vmm.pfn_db.lists.values())
            total_physical = active_count + list_counts
            items.append(TestResultItem(
                name=f"Scenario {s_id} Physical Frame Conservation (sum == 16)",
                expected="16 frames",
                actual=f"{total_physical} frames",
                passed=(total_physical == 16)
            ))

            # Validate TLB Entry Residency
            tlb_consistent = True
            for k in vmm.tlb.entries:
                proc = k // 100
                page = k % 100
                resident = any(
                    f.s == PfnState.ACTIVE and f.p == proc and f.pg == page
                    for f in vmm.pfn_db.frames
                )
                if not resident:
                    tlb_consistent = False
                    break

            items.append(TestResultItem(
                name=f"Scenario {s_id} TLB Residency Consistency",
                expected="All entries resident",
                actual="Consistent" if tlb_consistent else "Stale entries found",
                passed=tlb_consistent
            ))

        total = len(items)
        passed = sum(1 for it in items if it.passed)
        failed = total - passed
        rate = round((passed / total) * 100.0, 1) if total > 0 else 0.0

        return TestSuiteReport(
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            success_rate_pct=rate,
            results=items
        )
