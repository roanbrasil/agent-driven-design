"""
Compare FraudAgent v1, v2, and v3 side by side.

Shows the HDD improvement progression: what changed in the Harness at each step,
and what the eval numbers looked like before and after.

This is the ADD development loop in action:
  Observe → Inspect traces → Hypothesize Harness fix → Implement → Measure → Repeat.

Run from the project root:
    python reference/scripts/compare_versions.py

This runs all three versions against the full golden dataset. It makes real API calls.
Expect ~60 calls total (20 cases x 3 versions). With claude-haiku this is fast and cheap.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from reference.evals.runner import run_suite, load_golden_dataset

VERSIONS = ["v1", "v2", "v3"]

HDD_CHANGES = {
    "v1": [
        "Baseline: minimal system prompt, 1 tool (get_transaction_details)",
        "Model receives: transaction amount, merchant category, country",
        "Model does NOT receive: velocity, cardholder profile, merchant risk"
    ],
    "v2": [
        "HDD Round 1: structured decision criteria with thresholds in system prompt",
        "Added tool: get_cardholder_profile() — typical spend, home country",
        "Added tool: get_velocity_data() — 60-min and 24-hour counts with thresholds",
        "Added tool: get_merchant_risk() — chargeback rate, risk tier",
        "Prompt now tells the Model what signals to check and in what order"
    ],
    "v3": [
        "HDD Round 2: cardholder profile now includes active_travel_countries",
        "Added travel exception rule: if country in active_travel_countries → geography clears",
        "Added corporate card detection: typical_spend > $1000 → higher amount threshold",
        "Travel cases (TC-004, TC-011, TC-015) now pass — data was always there, Harness wasn't fetching it"
    ]
}

LLMDD_ANALYSIS = """
After v3: 90% pass rate (18/20). Remaining failures:

  TC-017 — Impossible travel (card used in US and Germany within 30 minutes)
            Harness fix available: add get_recent_transactions() to detect geo-impossible velocity.
            This is still HDD territory. LLMDD not yet warranted.

  TC-020 — Borderline: $380 at electronics (2x typical), velocity=4 (below threshold of 5),
            medium-risk merchant. Decision is judgment-dependent. Multiple reasonable outcomes.
            A human expert panel disagrees on this case.

When to consider LLMDD:
  - After adding get_recent_transactions() for impossible travel detection
  - If eval score plateaus at 90-92% despite multiple Harness iterations
  - If the Model consistently fails a specific class of ambiguous cases
    even when all relevant context is provided
  - Specifically: if TC-020-style edge cases cluster, and a fine-tuned model
    on 200+ labeled ambiguous traces would outperform the base model with
    the same Harness

The signal for LLMDD is: eval fails, context is correct, Model still gets it wrong.
The signal for HDD is: eval fails, and the Harness isn't giving the Model what it needs.
"""


def main():
    print("\n" + "=" * 70)
    print("  ADD Reference System — HDD Progression Comparison")
    print("=" * 70)
    print("\nRunning all three versions against the golden dataset (20 cases each)...")
    print("This makes real API calls. Expect 60 total calls to claude-haiku.\n")

    results = {}
    for version in VERSIONS:
        print(f"--- {version} ---")
        results[version] = run_suite(version)
        print()

    print("\n" + "=" * 70)
    print("  RESULTS COMPARISON")
    print("=" * 70)

    print(f"\n{'Version':<10} {'Output Pass%':<16} {'Traj Pass%':<14} {'Failures'}")
    print("-" * 60)

    for version in VERSIONS:
        summary = results[version]["summary"]
        oe = summary["output_eval"]
        te = summary["trajectory_eval"]
        failures = [f["case_id"] for f in oe.get("failures", [])]
        fail_str = ", ".join(failures) if failures else "none"
        print(
            f"{version:<10} "
            f"{oe['pass_rate']*100:.0f}% ({oe['passed']}/{oe['total']}){'':<5} "
            f"{te['pass_rate']*100:.0f}% ({te['passed']}/{te['total']}){'':<4} "
            f"{fail_str}"
        )

    print("\n" + "=" * 70)
    print("  HARNESS CHANGES — WHAT CHANGED AND WHY")
    print("=" * 70)

    for version in VERSIONS:
        oe = results[version]["summary"]["output_eval"]
        print(f"\n{version}: {oe['pass_rate']*100:.0f}% pass rate")
        for change in HDD_CHANGES[version]:
            print(f"  + {change}")

    print("\n" + "=" * 70)
    print("  WHEN TO CONSIDER LLMDD (LLM-Driven Design)")
    print("=" * 70)
    print(LLMDD_ANALYSIS)


if __name__ == "__main__":
    main()
