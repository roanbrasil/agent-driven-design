"""
Eval runner: loads the golden dataset and runs all evals against a given agent version.

Usage (from reference/):
    python -m evals.runner --version v3
    python -m evals.runner --version v2 --judge   (includes LLM-as-Judge, costs API calls)
    python -m evals.runner --version v1 --cases TC-001,TC-002
"""

import json
import sys
import os
import argparse
from dataclasses import asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from reference.domain.models import (
    Transaction, CardProfile, VelocityData, MerchantRisk, EvalCase, FraudDecision
)
from reference.observability.tracer import Trace
from reference.evals import output_eval, trajectory_eval, llm_judge


def load_golden_dataset(path: str = None) -> list[EvalCase]:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "domain", "golden_dataset.json")

    with open(path) as f:
        raw = json.load(f)

    cases = []
    for item in raw:
        tx = item["transaction"]
        cp = item["card_profile"]
        v = item["velocity"]
        mr = item["merchant_risk"]

        cases.append(EvalCase(
            case_id=item["case_id"],
            description=item["description"],
            difficulty=item.get("difficulty", "normal"),
            expected_decision=item["expected_decision"],
            expected_signals=item.get("expected_signals", []),
            transaction=Transaction(**tx),
            card_profile=CardProfile(**cp),
            velocity=VelocityData(**v),
            merchant_risk=MerchantRisk(**mr)
        ))

    return cases


def load_agent(version: str):
    if version == "v1":
        from reference.agents.fraud_agent.v1 import agent
    elif version == "v2":
        from reference.agents.fraud_agent.v2 import agent
    elif version == "v3":
        from reference.agents.fraud_agent.v3 import agent
    else:
        raise ValueError(f"Unknown version: {version}. Choose v1, v2, or v3.")
    return agent


def run_single_case(agent_module, case: EvalCase, version: str, use_judge: bool = False) -> dict:
    trace = Trace()
    trace.agent_version = version
    trace.transaction_id = case.transaction.transaction_id

    decision = agent_module.run(
        transaction=case.transaction,
        card_profile=case.card_profile,
        velocity=case.velocity,
        merchant_risk=case.merchant_risk,
        tracer=trace.steps
    )

    trace.complete(decision.decision)

    output_result = output_eval.run(decision, case, trace)
    traj_result = trajectory_eval.run(decision, case, trace)

    result = {
        "case_id": case.case_id,
        "description": case.description,
        "difficulty": case.difficulty,
        "output": output_result,
        "trajectory": traj_result,
        "trace": trace.to_dict()
    }

    if use_judge:
        judge_result = llm_judge.run(decision, case, trace)
        result["judge"] = judge_result

    return result


def run_suite(version: str, case_filter: list = None, use_judge: bool = False) -> dict:
    cases = load_golden_dataset()
    if case_filter:
        cases = [c for c in cases if c.case_id in case_filter]

    agent_module = load_agent(version)

    results = []
    for case in cases:
        print(f"  Running {case.case_id} ({case.difficulty})...", end=" ", flush=True)
        result = run_single_case(agent_module, case, version, use_judge)
        status = "PASS" if result["output"]["passed"] else "FAIL"
        print(status)
        results.append(result)

    output_results = [r["output"] for r in results]
    traj_results = [r["trajectory"] for r in results]

    summary = {
        "version": version,
        "output_eval": output_eval.summarize(output_results),
        "trajectory_eval": trajectory_eval.summarize(traj_results),
    }

    if use_judge:
        judge_results = [r["judge"] for r in results if "judge" in r]
        if judge_results:
            summary["llm_judge"] = llm_judge.summarize(judge_results)

    return {"summary": summary, "results": results}


def print_summary(suite_result: dict):
    s = suite_result["summary"]
    version = s["version"]

    print(f"\n{'='*60}")
    print(f"  FraudAgent {version} — Eval Summary")
    print(f"{'='*60}")

    oe = s["output_eval"]
    print(f"\nOutput Eval:      {oe['passed']}/{oe['total']} passed ({oe['pass_rate']*100:.0f}%)")
    print(f"By difficulty:    {oe['by_difficulty']}")

    if oe["failures"]:
        print(f"\nFailures:")
        for f in oe["failures"]:
            print(f"  {f['case_id']}: expected {f['expected']}, got {f['actual']} — {f['description'][:60]}")

    te = s["trajectory_eval"]
    print(f"\nTrajectory Eval:  {te['passed']}/{te['total']} passed ({te['pass_rate']*100:.0f}%)")
    print(f"Avg traj score:   {te['avg_score']:.2f}")
    if te["most_common_issues"]:
        print(f"Common issues:    {te['most_common_issues'][:3]}")

    if "llm_judge" in s:
        je = s["llm_judge"]
        print(f"\nLLM-as-Judge:     {je['passed']}/{je['total']} passed ({je['pass_rate']*100:.0f}%)")
        print(f"Avg judge score:  {je['avg_score_5']}")
        if je["low_quality_cases"]:
            print(f"Low quality (<= 2):")
            for lq in je["low_quality_cases"]:
                print(f"  {lq['case_id']}: score={lq['score']} — {lq['reason']}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run evals against a FraudAgent version.")
    parser.add_argument("--version", choices=["v1", "v2", "v3"], required=True)
    parser.add_argument("--judge", action="store_true", help="Include LLM-as-Judge (costs API calls).")
    parser.add_argument("--cases", help="Comma-separated list of case IDs to run (default: all).")
    parser.add_argument("--output", help="Save full results to a JSON file.")
    args = parser.parse_args()

    case_filter = args.cases.split(",") if args.cases else None

    print(f"\nRunning FraudAgent {args.version} against golden dataset...")
    if case_filter:
        print(f"Filtering to: {case_filter}")

    suite_result = run_suite(args.version, case_filter, args.judge)
    print_summary(suite_result)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(suite_result, f, indent=2, default=str)
        print(f"Full results saved to: {args.output}")
