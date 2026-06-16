"""
LLM-as-Judge for the ADD reference system.

The judge is a Conditional Agent. It has its own context boundary, its own
system prompt, and its own output schema. It evaluates reasoning quality —
something no deterministic eval can measure.

A fraud decision can be CORRECT (right call) but show POOR REASONING
(arrived there without citing the signals that justify it). The judge
catches that. Output evals do not.
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import anthropic
from reference.domain.models import FraudDecision, EvalCase
from reference.observability.tracer import Trace

client = anthropic.Anthropic()

JUDGE_SYSTEM = """You are an evaluation judge for a credit card fraud detection agent.

You assess the REASONING QUALITY of fraud decisions, not just whether the decision is correct.
A correct decision with poor reasoning is a reliability risk — next time, the same shallow
reasoning may produce a wrong decision.

CALIBRATION EXAMPLES:

Example A (score 5):
Decision: BLOCK
Reasoning: "Velocity is 8 transactions in 60 minutes (threshold: 5). Merchant chargeback
rate is 4.2% (threshold: 3%). Amount is $892, which is 6.1x the cardholder's typical
spend of $146. Three independent signals all point to high fraud risk."
Why score 5: All three relevant signals cited with specific numbers. Clear threshold
comparisons. The reasoning would generalize correctly to similar cases.

Example B (score 3):
Decision: BLOCK
Reasoning: "This transaction looks suspicious based on the history and the amount."
Why score 3: Correct decision. Vague reasoning. No specific numbers cited. Would not
help diagnose the agent's behavior or predict future decisions.

Example C (score 1):
Decision: APPROVE
Reasoning: "The transaction seems legitimate."
Why score 1: Wrong decision on a clear fraud case, AND no reasoning provided.

Now score the following response.

Respond with valid JSON:
{
  "score": <1-5>,
  "reason": "<one sentence explaining the score>",
  "passed": <true if score >= 3>,
  "signals_cited": ["list of specific signals the agent mentioned by name"],
  "numbers_cited": <true if the agent cited at least one specific number>
}"""

FRAUD_RUBRIC = """Score the fraud agent's reasoning quality:

5: Decision is correct AND reasoning cites specific data points (velocity count,
   chargeback rate, amount vs typical) with concrete numbers and threshold comparisons.
4: Correct decision, cites most relevant signals, minor gaps in specificity.
3: Correct decision, reasoning present but shallow — signals named but not quantified.
2: Correct decision but reasoning is confused, contradictory, or doesn't cite the
   signals that actually justify it.
1: Wrong decision, OR correct decision with no reasoning, OR output is malformed."""


def judge(task: str, response: str, trace: Trace = None) -> dict:
    """
    Judge a single agent response. Returns a score dict.
    If a trace is provided, attaches the score to it.
    """
    result = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=JUDGE_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"TASK:\n{task}\n\nRESPONSE:\n{response}\n\nRUBRIC:\n{FRAUD_RUBRIC}"
        }]
    )

    text = result.content[0].text
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"score": 1, "reason": "Judge returned malformed output.", "passed": False, "signals_cited": [], "numbers_cited": False}

    if trace is not None:
        trace.attach_score(
            eval_name="llm_judge",
            score=data["score"] / 5.0,
            passed=data.get("passed", False),
            reason=data.get("reason", "")
        )

    return data


def panel_judge(task: str, response: str, trace: Trace = None, n: int = 3) -> dict:
    """
    Run n independent judge calls and aggregate by majority vote.
    Use for production gate evals where a single judge run has too much variance.
    """
    scores = [judge(task, response) for _ in range(n)]
    numeric = [s["score"] for s in scores]
    avg = sum(numeric) / len(numeric)
    passed_votes = sum(1 for s in scores if s.get("passed", False))
    majority_passed = passed_votes >= (n // 2 + 1)

    result = {
        "scores": numeric,
        "average": round(avg, 2),
        "passed": majority_passed,
        "reasons": [s["reason"] for s in scores],
        "panel_size": n
    }

    if trace is not None:
        trace.attach_score(
            eval_name="llm_judge_panel",
            score=avg / 5.0,
            passed=majority_passed,
            reason=f"Panel ({n}): avg={avg:.1f}, votes_passed={passed_votes}/{n}"
        )

    return result


def build_task_description(case: EvalCase) -> str:
    return (
        f"Evaluate transaction {case.transaction.transaction_id} for fraud.\n"
        f"Amount: ${case.transaction.amount:.2f} at {case.transaction.merchant_category} merchant.\n"
        f"Country: {case.transaction.country}.\n"
        f"Correct decision: {case.expected_decision}."
    )


def run(decision: FraudDecision, case: EvalCase, trace: Trace) -> dict:
    """
    Full judge eval for one case. Returns the judge's assessment.
    """
    task = build_task_description(case)
    response = f"Decision: {decision.decision}\nReasoning: {decision.reasoning}\nSignals: {', '.join(decision.signals_used)}"

    result = judge(task, response, trace)
    result["case_id"] = case.case_id
    result["output_correct"] = decision.decision == case.expected_decision
    return result


def summarize(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.get("passed", False))
    scores = [r.get("score", 0) for r in results]
    avg = sum(scores) / total if total > 0 else 0.0

    low_quality = [r for r in results if r.get("score", 5) <= 2]

    return {
        "pass_rate": passed / total if total > 0 else 0.0,
        "passed": passed,
        "total": total,
        "avg_score": round(avg, 2),
        "avg_score_5": f"{avg:.1f}/5",
        "low_quality_cases": [
            {"case_id": r["case_id"], "score": r.get("score"), "reason": r.get("reason", "")}
            for r in low_quality
        ]
    }
