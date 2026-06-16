"""
Trajectory eval: did the agent take the right path to reach its decision?

Output evals miss two failure classes:
  1. Right answer through wrong reasoning (lucky this time, catastrophic next time)
  2. Wrong tool call sequence (redundant calls, missing required tools, wrong order)

Trajectory evals are more expensive to write and maintain. Run them for the
behaviors that matter most: required tool sequences, unnecessary calls, efficiency.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from reference.domain.models import FraudDecision, EvalCase
from reference.observability.tracer import Trace


REQUIRED_TOOLS_BY_VERSION = {
    "v1": ["get_transaction_details"],
    "v2": ["get_transaction_details", "get_cardholder_profile", "get_velocity_data", "get_merchant_risk"],
    "v3": ["get_transaction_details", "get_cardholder_profile", "get_velocity_data", "get_merchant_risk"]
}

MAX_MODEL_CALLS = 5


def run(decision: FraudDecision, case: EvalCase, trace: Trace) -> dict:
    """
    Evaluate the trajectory of a single agent run.
    Checks: required tools called, no redundant calls, efficiency.
    """
    version = trace.agent_version
    tool_calls = trace.tool_calls()
    tools_used = [t["tool"] for t in tool_calls]
    model_calls = trace.model_calls()

    required = REQUIRED_TOOLS_BY_VERSION.get(version, [])

    missing_tools = [t for t in required if t not in tools_used]
    redundant_calls = _find_redundant_calls(tool_calls)
    efficiency_ok = model_calls <= MAX_MODEL_CALLS

    issues = []
    if missing_tools:
        issues.append(f"missing required tools: {missing_tools}")
    if redundant_calls:
        issues.append(f"redundant tool calls: {redundant_calls}")
    if not efficiency_ok:
        issues.append(f"too many model calls: {model_calls} (max {MAX_MODEL_CALLS})")

    passed = len(issues) == 0
    score = _compute_score(missing_tools, redundant_calls, efficiency_ok)

    result = {
        "case_id": case.case_id,
        "transaction_id": decision.transaction_id,
        "passed": passed,
        "score": score,
        "tools_used": tools_used,
        "missing_tools": missing_tools,
        "redundant_calls": redundant_calls,
        "model_calls": model_calls,
        "issues": issues
    }

    trace.attach_score(
        eval_name="trajectory_eval",
        score=score,
        passed=passed,
        reason="; ".join(issues) if issues else "trajectory clean"
    )

    return result


def _find_redundant_calls(tool_calls: list) -> list:
    seen = {}
    redundant = []
    for call in tool_calls:
        key = (call["tool"], str(call.get("input", {})))
        if key in seen:
            redundant.append(call["tool"])
        seen[key] = True
    return redundant


def _compute_score(missing: list, redundant: list, efficiency_ok: bool) -> float:
    score = 1.0
    score -= len(missing) * 0.25
    score -= len(redundant) * 0.1
    if not efficiency_ok:
        score -= 0.2
    return max(0.0, round(score, 2))


def summarize(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    avg_score = sum(r["score"] for r in results) / total if total > 0 else 0.0

    all_issues = []
    for r in results:
        all_issues.extend(r["issues"])

    issue_counts = {}
    for issue in all_issues:
        issue_counts[issue] = issue_counts.get(issue, 0) + 1

    return {
        "pass_rate": passed / total if total > 0 else 0.0,
        "passed": passed,
        "total": total,
        "avg_score": round(avg_score, 3),
        "most_common_issues": sorted(issue_counts.items(), key=lambda x: -x[1])[:5]
    }
