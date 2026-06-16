"""
CLI entrypoint for running evals against a single FraudAgent version.

Delegates to evals/runner.py with a friendlier interface.

Run from the project root:
    python reference/scripts/run_evals.py --version v3
    python reference/scripts/run_evals.py --version v2 --judge
    python reference/scripts/run_evals.py --version v1 --cases TC-001,TC-002,TC-003
    python reference/scripts/run_evals.py --version v3 --output results_v3.json
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import argparse
from reference.evals.runner import run_suite, print_summary
import json


def main():
    parser = argparse.ArgumentParser(
        description="Run evals for the ADD FraudAgent reference system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Run v3 output + trajectory evals on all 20 golden cases:
    python reference/scripts/run_evals.py --version v3

  Run all evals including LLM-as-Judge (more API calls):
    python reference/scripts/run_evals.py --version v3 --judge

  Run only specific cases:
    python reference/scripts/run_evals.py --version v2 --cases TC-004,TC-011,TC-015

  Save full results to JSON for inspection:
    python reference/scripts/run_evals.py --version v3 --output results_v3.json
        """
    )
    parser.add_argument("--version", choices=["v1", "v2", "v3"], required=True,
                        help="FraudAgent version to evaluate.")
    parser.add_argument("--judge", action="store_true",
                        help="Include LLM-as-Judge scoring (makes additional API calls to claude-sonnet).")
    parser.add_argument("--cases", type=str,
                        help="Comma-separated case IDs to run. Default: all 20 cases.")
    parser.add_argument("--output", type=str,
                        help="Path to save full results JSON.")

    args = parser.parse_args()
    case_filter = [c.strip() for c in args.cases.split(",")] if args.cases else None

    print(f"\nFraudAgent {args.version} — Eval Run")
    print(f"Cases: {'all 20' if not case_filter else str(case_filter)}")
    print(f"Judge: {'yes (claude-sonnet-4-6)' if args.judge else 'no'}")
    print()

    suite_result = run_suite(args.version, case_filter, args.judge)
    print_summary(suite_result)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(suite_result, f, indent=2, default=str)
        print(f"Full results saved to: {args.output}\n")


if __name__ == "__main__":
    main()
