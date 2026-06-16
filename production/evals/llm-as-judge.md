# LLM-as-Judge

You have an agent that generates fraud decisions. Or draft emails. Or code reviews. How do you know if it is doing it well?

You could write deterministic checks: does the output contain an APPROVE or BLOCK token, is the JSON schema valid, did the agent call the right tools? Those checks are necessary. But they are not sufficient. They tell you the output has the right shape. They say nothing about whether the content is correct.

This is where LLM-as-Judge comes in. You use a second model to evaluate the quality of the first model's output. The judge reads the task, the agent's response, and a scoring rubric, and returns a score with a reason.

It sounds almost too simple. It also works surprisingly well, and it fails in predictable ways that you can engineer around. Here is everything you need to know.

---

## The ADD framing

In ADD terms, the judge is a Conditional Agent.

It has its own context boundary. It receives a structured input (the task, the response, the rubric) and produces a structured output (a score, a reason). It does not affect the primary agent's behavior. It can fail without bringing down the system. It runs after the fact, not in the critical path.

This means all the rules that apply to any agent apply to the judge:

- Its system prompt is a Harness responsibility
- Its output schema is an Agent Contract
- Its tool surface is narrow (usually no tools at all)
- Its evals are separate from the evals it is judging

Yes, you need evals for your judge. We will get there.

---

## Anatomy of a judge

A judge has three inputs and one output.

**Inputs:**
1. The original task (what the agent was asked to do)
2. The agent's response (what it produced)
3. The rubric (how to score the response)

**Output:**
1. A score (numeric or categorical)
2. A reason (natural language explanation of the score)

That is it. The judge does not call tools. It does not remember previous evaluations. It reads, reasons, scores.

```python
JUDGE_SYSTEM = """You are an evaluation judge. You assess the quality of AI agent responses.

You will receive:
- TASK: what the agent was asked to do
- RESPONSE: what the agent produced
- RUBRIC: the criteria to evaluate against

Score the response from 1 to 5 using the rubric. Return JSON:
{
  "score": <1-5>,
  "reason": "<one sentence explaining the score>",
  "passed": <true if score >= 3>
}

Be strict. A score of 5 means the response is exemplary, not merely correct.
A score of 3 means acceptable but improvable. Reserve 1 and 2 for clear failures."""


def judge(task: str, response: str, rubric: str) -> dict:
    result = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=JUDGE_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"TASK:\n{task}\n\nRESPONSE:\n{response}\n\nRUBRIC:\n{rubric}"
        }]
    )
    return json.loads(result.content[0].text)
```

Three things worth noting in this implementation:

The judge returns structured output. Parsing a score out of prose is fragile. Force JSON from the start. If the judge cannot produce valid JSON, treat it as an eval failure, not a score of zero.

The judge has a strict system prompt. "Be strict" and "reserve 1 and 2 for clear failures" are not filler. Without these constraints, judges drift toward the middle. Every response becomes a 3. Your score distribution tells you nothing.

The judge does not receive the reference answer yet. For some eval types you want the judge blind to the ground truth. For others you want it to compare. That is a rubric design decision, not a judge architecture decision.

---

## Writing rubrics that work

The rubric is where most LLM-as-Judge implementations fail. Teams write rubrics like this:

```
Rate the response on clarity, accuracy, and helpfulness from 1 to 5.
```

This rubric will produce inconsistent scores. "Clarity" means different things to different judges. "Accuracy" without a reference is unmeasurable. "Helpfulness" is entirely subjective.

A good rubric is specific, anchored, and decomposed.

**Specific:** Define exactly what you are measuring. Not "accuracy" but "does the response correctly identify whether the transaction should be blocked based on the velocity and merchant risk data provided?"

**Anchored:** Give concrete examples for each score level. The judge should not have to infer what a 4 looks like.

**Decomposed:** For complex responses, score multiple dimensions separately and aggregate. A response can be factually correct but poorly structured. Forcing a single score collapses the signal.

Here is a rubric for the fraud agent from the HDD vs LLMDD guide:

```python
FRAUD_DECISION_RUBRIC = """
Score the fraud agent's decision on the following criteria:

DECISION CORRECTNESS (required):
- Does the response output exactly APPROVE or BLOCK?
- If not, score is 1 regardless of other factors.

REASONING QUALITY (1-5):
5: Cites specific data points (velocity count, merchant chargeback rate, amount vs typical spend),
   explains why each data point supports the decision, no irrelevant information.
4: Cites most relevant data points, reasoning is sound, minor gaps.
3: Decision is correct but reasoning is shallow or partially supported.
2: Decision may be correct but reasoning is confused, contradictory, or missing.
1: Wrong decision, or correct decision with reasoning that would not generalize.

Return a score for REASONING QUALITY assuming DECISION CORRECTNESS passes.
If DECISION CORRECTNESS fails, return score 1 with reason "invalid output format".
"""
```

This rubric fails fast (decision correctness check) and then scores the thing that actually matters for improving the agent (reasoning quality). The score levels are concrete. A different person reading this rubric would produce similar scores.

---

## The bias problem

LLM judges have well-documented biases. Ignoring them makes your evals unreliable. Understanding them lets you design around them.

**Position bias.** When the judge sees multiple responses to compare, it favors the one that appears first. Fix: randomize the order across eval runs and average.

**Verbosity bias.** Longer responses tend to score higher even when a shorter response is more correct. Fix: add an explicit instruction to your rubric: "a concise correct answer outscores a verbose partially-correct one."

**Self-enhancement bias.** When using the same model as both the agent and the judge, the judge tends to rate outputs from its own model family higher. Fix: use a different model family for the judge when possible, or run cross-model validation.

**Sycophancy.** If the rubric mentions what the "expected" answer is before asking for a score, the judge anchors to it even when the agent's answer is actually better. Fix: when comparing to a reference, present both anonymously and ask which is better before revealing which is which.

**Rubric drift.** Over many evaluations, judges interpret rubric language differently depending on what they have seen recently. Fix: include 2 to 3 calibration examples in the system prompt showing what a 2, 3, and 5 look like for your specific task.

```python
JUDGE_SYSTEM_WITH_CALIBRATION = """You are an evaluation judge for a fraud detection agent.

CALIBRATION EXAMPLES:

Example A (score 5):
Task: Evaluate transaction TX-9821 for fraud risk.
Response: BLOCK. Velocity is 8 transactions in 60 minutes (threshold: 5).
         Merchant chargeback rate is 4.2% (threshold: 3%). Amount is $892,
         which is 6.1x the cardholder's typical spend of $146. Three independent
         signals all point to high fraud risk.
Why score 5: Correct decision. All three relevant data points cited with specific
             numbers. Clear threshold comparisons. No irrelevant information.

Example B (score 3):
Task: Evaluate transaction TX-4421 for fraud risk.
Response: BLOCK. This looks suspicious based on the transaction history.
Why score 3: Correct decision. Vague reasoning. No specific data points cited.
             Would not help diagnose why the agent got the right answer.

Example C (score 1):
Task: Evaluate transaction TX-2291 for fraud risk.
Response: The transaction has some risk factors but also some legitimate signals.
          I would recommend further review.
Why score 1: No decision produced. Agent failed its core task.

Now evaluate the following response using the same standards..."""
```

Three calibration examples in the system prompt take 30 minutes to write and cut score variance significantly. Do it.

---

## Panel judges vs single judges

A single judge run on a single response gives you one data point. That data point has variance. Run the same judge on the same response twice and you will sometimes get different scores.

For high-stakes evals, run a panel: three independent judge calls on the same response, then aggregate. The aggregation strategy matters:

**Majority vote** works well for categorical scores (PASS/FAIL). If two of three judges say FAIL, the response fails.

**Average** works for numeric scores when you want a continuous signal. But outliers from a confused judge run can distort the average. Consider dropping the highest and lowest score and averaging the middle one.

**Consensus required** is appropriate when the cost of a false positive is high. All three judges must agree for the response to pass. More conservative, generates more review work.

```python
def panel_judge(task: str, response: str, rubric: str, n: int = 3) -> dict:
    scores = [judge(task, response, rubric) for _ in range(n)]
    numeric_scores = [s["score"] for s in scores]
    avg = sum(numeric_scores) / len(numeric_scores)
    passed = sum(1 for s in scores if s["passed"]) >= (n // 2 + 1)  # majority

    return {
        "scores": numeric_scores,
        "average": avg,
        "passed": passed,
        "reasons": [s["reason"] for s in scores]
    }
```

When should you use a panel? When the cost of being wrong about a score is high. For exploratory evals during development, a single judge is fine. For the regression suite that gates a production deploy, run a panel.

---

## Reference-based vs reference-free judging

There are two modes of LLM-as-Judge evaluation. Choosing the wrong one gives you wrong results.

**Reference-free judging** asks the judge to evaluate the response on its own merits against the rubric. No ground truth required. This works well when:
- Ground truth is expensive or impossible to produce
- The task is generative (writing, summarization, explanation) where multiple correct answers exist
- You are measuring dimensions like reasoning quality, not factual correctness

**Reference-based judging** asks the judge to compare the response to a known-correct reference answer. The judge says whether the response agrees with, contradicts, or partially captures the reference. This works well when:
- You have a golden dataset with verified correct answers
- Factual accuracy is the primary evaluation dimension
- You are checking whether the agent retrieves the right information

The worst pattern is using reference-based judging without high-quality references. A mediocre reference answer will cause the judge to penalize correct responses that happen to phrase things differently. Build your golden dataset carefully before relying on reference-based evals.

---

## Judging trajectory, not just output

Output-only evaluation is a local maximum. An agent can reach the right final answer through broken reasoning. An agent can fail to reach the right answer even with correct reasoning if the Harness has a bug in output parsing. Output scores hide this.

Trajectory evaluation scores the agent's path: which tools were called, in what order, with what inputs, producing what results.

The judge receives the full trace, not just the final output.

```python
def judge_trajectory(task: str, trace: list[dict], final_output: str, rubric: str) -> dict:
    trace_summary = "\n".join([
        f"Step {i+1}: {step['type']} | {step.get('tool', '')} | {step.get('result', '')[:100]}"
        for i, step in enumerate(trace)
    ])

    return judge(
        task=task,
        response=f"TRAJECTORY:\n{trace_summary}\n\nFINAL OUTPUT:\n{final_output}",
        rubric=rubric
    )
```

What to score in a trajectory eval:

**Tool call necessity.** Did the agent call tools it did not need? A fraud agent that calls `get_weather` is broken regardless of its final decision. Score unnecessary tool calls as a failure.

**Tool call order.** Some sequences matter. An agent that tries to analyze data before retrieving it is working with stale context. Score ordering failures.

**Retrieval relevance.** When the agent uses RAG tools, did it retrieve the right chunks? A high-quality final answer built on irrelevant retrievals is a lucky accident, not a reliable behavior.

**Iteration efficiency.** In a ReAct loop, how many steps did the agent take? An agent that reaches the right answer in 12 steps when 3 are sufficient is fragile at scale.

Trajectory evals are more expensive to run and harder to write rubrics for. They are also the only way to catch a class of bugs that output evals will never surface.

---

## Evals for your judge

Your judge is an agent. Agents need evals.

Judge evals measure inter-rater reliability: does your judge agree with human ratings? The process:

1. Take 50 to 100 agent responses from your production traces
2. Have domain experts label each one with a score
3. Run your judge on the same responses
4. Measure agreement: correlation for numeric scores, kappa for categorical

A judge with less than 0.7 correlation to human labels is producing noise. Fix the rubric or the calibration examples before trusting the judge on new data.

The second eval for a judge is consistency: does it give the same score for the same response on repeated runs?

```python
def eval_judge_consistency(task: str, response: str, rubric: str, runs: int = 5) -> dict:
    scores = [judge(task, response, rubric)["score"] for _ in range(runs)]
    variance = max(scores) - min(scores)
    return {
        "scores": scores,
        "variance": variance,
        "consistent": variance <= 1  # allow at most 1 point variation
    }
```

A variance of more than 1 point on a 5-point scale for the same input means your rubric is underspecified. Tighten it.

---

## Connecting the judge to the improvement cycle

The judge is useful only if it drives decisions. Here is how it connects to HDD and LLMDD:

When judge scores drop after a Harness change (new prompt version, new tool added), you have a Harness regression. Roll back the change, diagnose with trace inspection, and iterate.

When judge scores are consistently low on a specific task type despite multiple Harness iterations, you have a Model problem. The input the judge is evaluating is being produced by a Model that cannot handle that task type reliably. This is the signal to consider LLMDD.

When judge scores are high but human satisfaction is low, your rubric is wrong. The judge is optimizing for something that is not what users actually care about. Fix the rubric before making any other change.

The judge does not tell you what to fix. It tells you that something is wrong and roughly where. Traces tell you exactly what.

---

## At a glance

| Decision | Answer |
|---|---|
| Reference-free or reference-based? | Reference-free for generative tasks; reference-based when you have a verified golden set |
| Single judge or panel? | Single for development; panel (n=3, majority) for production gates |
| Same model as agent? | Use a different model family when possible to avoid self-enhancement bias |
| How many calibration examples? | 2 to 3 anchored examples in the system prompt per rubric |
| Output-only or trajectory? | Trajectory for behavior-critical agents; output-only for initial development |
| How to know if the judge is working? | Measure correlation with human labels on a labeled sample |

See also: [Evals in ADD](./README.md) · [Observability](../observability/README.md) · [HDD vs LLMDD](../../guides/hdd-vs-ldd.md)
