"""
Output eval: did the agent produce the correct APPROVE or BLOCK decision?

This is your baseline eval layer. Start here. It tells you whether the agent
is getting the answer right, not whether it's getting it right for the right reasons.
That's trajectory_eval's job.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from reference.domain.models import FraudDecision, EvalCase
from reference.observability.tracer import Trace


def run(decision: FraudDecision, case: EvalCase, trace: Trace) -> dict:
    """
    Evaluate the output of a single agent run against a golden dataset case.
    Returns a result dict and attaches the score to the trace.
    """
    correct = decision.decision == case.expected_decision

    result = {
        "case_id": case.case_id,
        "transaction_id": decision.transaction_id,
        "expected": case.expected_decision,
        "actual": decision.decision,
        "passed": correct,
        "difficulty": case.difficulty,
        "description": case.description
    }

    trace.attach_score(
        eval_name="output_eval",
        score=1.0 if correct else 0.0,
        passed=correct,
        reason=f"Expected {case.expected_decision}, got {decision.decision}"
    )

    return result


def summarize(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    by_difficulty = {}

    for r in results:
        d = r["difficulty"]
        if d not in by_difficulty:
            by_difficulty[d] = {"total": 0, "passed": 0}
        by_difficulty[d]["total"] += 1
        if r["passed"]:
            by_difficulty[d]["passed"] += 1

    failures = [r for r in results if not r["passed"]]

    return {
        "pass_rate": passed / total if total > 0 else 0.0,
        "passed": passed,
        "total": total,
        "by_difficulty": {
            d: f"{v['passed']}/{v['total']}" for d, v in by_difficulty.items()
        },
        "failures": [
            {"case_id": r["case_id"], "expected": r["expected"], "actual": r["actual"], "description": r["description"]}
            for r in failures
        ]
    }
