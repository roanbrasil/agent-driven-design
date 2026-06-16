# Evals in ADD

Most teams start writing evals too late, in the wrong order, and measuring the wrong thing. They build a working agent, ship it, watch it fail in production, and then scramble to write tests that should have existed from day one.

Here is the right way to think about evals for agentic systems. What to measure, when to measure it, and how to avoid the traps that make eval suites expensive to maintain and easy to game.

---

## The three levels of evaluation

ADD distinguishes three distinct evaluation targets. Conflating them is the most common eval mistake because each level catches a different class of failure and points to a different fix.

### 1. Model eval

Tests the Model in isolation. Given a fixed prompt with no tools and no Harness context, does the Model produce the right output?

Use for: model selection, regression testing after a model upgrade, checking whether a capability exists at the Model level before building Harness around it.

Limitation: the Model never runs in isolation in production. A Model eval that passes says nothing about whether the agent works. It tells you the raw material is good. What you build with it is a separate question.

### 2. Agent eval

Tests the full Agent (Model plus Harness) end to end. Given a real user task, does the agent produce the right final output?

This is your primary eval layer. It runs the full loop: tool calls, memory retrieval, output parsing, loop control. When something breaks in production, an agent eval is almost always what would have caught it.

Use for: detecting regressions after Harness changes (prompt edits, new tools, routing changes), validating that a new agent behavior works as intended, catching boundary violations.

### 3. System eval

Tests a full multi-agent topology end to end. Given an end-to-end task that crosses agent boundaries, does the system produce the right result?

Most expensive to run. Most representative of real production behavior. When system evals fail and agent evals pass, the problem is in the handoff: a contract violation, a translation error, a routing bug.

Use for: validating inter-agent contracts, catching topology regressions, testing failure modes (what happens when a worker agent times out?).

---

## The eval decision rule

When an eval fails, the level tells you where to look:

```
Eval fails
    |
    +-- Model eval fails
    |       The Model cannot do the task given the right prompt.
    |       Fix: better base model or LLMDD (fine-tuning).
    |
    +-- Agent eval fails but Model eval passes
    |       The Model can do the task but the agent cannot.
    |       Fix: HDD (prompt, tools, context, routing).
    |
    +-- System eval fails but Agent evals pass
            Each agent works but the system does not.
            Fix: inter-agent contracts, topology, routing logic.
```

Run in this order. Do not investigate system evals when you have unresolved agent eval failures. The noise makes diagnosis impossible.

---

## Building a golden dataset

Your evals are only as good as your test cases. A golden dataset is a curated set of (input, expected output) pairs that you trust enough to gate deploys on.

Building one takes real work. Here is the process that produces a dataset worth trusting:

**Start with production traces.** Your best test cases are things users actually asked. Export 200 to 300 traces from your first weeks of production. These are real inputs with real variety. Synthetic inputs miss the distribution.

**Label them correctly.** For each trace, a domain expert (not the model, not the developer) decides: was this response correct? What would the correct response look like? This labeling is the expensive step. Do not skip it or delegate it to an LLM without human validation.

**Stratify your sample.** Make sure your golden set covers:
- Common cases (should be easy)
- Edge cases you know about (tricky inputs that caused failures before)
- Adversarial inputs (inputs designed to confuse the agent)
- Boundary cases (inputs where the right answer is genuinely ambiguous)

If your golden set is 95% easy common cases, your eval suite will pass confidently right up until the edge cases hit production.

**Version the dataset.** Treat your golden set like code. It lives in version control. Changes to it are reviewed. When you add new cases because of a production failure, note when and why they were added. A golden set that grows without tracking accumulates debt.

**Minimum viable size:** 50 labeled examples is enough to start. 200 is where you get reliable signal on regressions. Below 50, your pass rate is mostly noise.

---

## Output evals vs trajectory evals

Output evals check the final answer. Trajectory evals check the path.

An agent can produce the right final answer through broken reasoning. It can also fail to produce the right answer because of a bug in the Harness, even when the Model's reasoning was perfect. Output evals miss both failure modes.

Trajectory evals give you a much richer signal.

```python
def run_agent_eval(test_case: dict) -> dict:
    task = test_case["input"]
    expected = test_case["expected_output"]

    # Run the full agent, capturing the trace
    trace = []
    result = run_agent_with_trace(task, trace_collector=trace)

    return {
        "output_correct": result == expected,
        "tool_calls": [step for step in trace if step["type"] == "tool_use"],
        "loop_iterations": len([s for s in trace if s["type"] == "model_call"]),
        "unnecessary_tools": find_unnecessary_calls(trace, test_case),
        "correct_tool_order": check_tool_order(trace, test_case.get("expected_tool_sequence")),
    }
```

What trajectory evals catch that output evals miss:

**Unnecessary tool calls.** The agent called `get_cardholder_profile` three times in one transaction evaluation. The final answer was correct. The behavior is wrong and will cause latency and cost issues at scale.

**Wrong reasoning path to a right answer.** The agent approved a transaction. The transaction should have been approved. But it approved it because it misread the velocity number (8 was read as "within normal range" when the threshold is 5). Lucky this time. Catastrophic on the next transaction.

**Harness bugs masked by Model compensation.** The tool returned malformed JSON. The Model parsed the prose representation and somehow extracted the right value. The Harness bug exists; the output eval will never find it.

Start with output evals. Add trajectory evals for the behaviors that matter most. They are more expensive to write and maintain, but they catch a fundamentally different class of failures.

---

## Regression testing

Every production failure that gets fixed should produce a new eval case. This is non-negotiable.

The process:

1. Production failure happens. Agent makes wrong decision on transaction TX-4821.
2. Root cause found. Missing cardholder travel history in profile tool.
3. Harness fixed. Tool updated to include travel history.
4. New eval case added: TX-4821 with correct expected output.
5. Full eval suite run. TX-4821 now passes. No regressions in the other 200 cases.
6. Deploy.

Without step 4, you will fix the same bug twice. Production is a better test suite than you will ever write, but only if you capture what it teaches you.

Regression test naming matters. Name the test case after the incident, not after the technical issue. `test_international_transaction_frequent_traveler` is more useful than `test_travel_history_field`. Six months from now, the name is the only documentation you have.

---

## Eval-driven development

The right time to write evals is before you write the agent. Or at least before you ship it.

The process looks like this:

**Define success first.** Before writing a single line of Harness code, write down: what does a correct agent response look like? What would make it wrong? What are the top 5 inputs you want it to handle? This thinking produces the first version of your rubric and the first 5 golden examples.

**Use evals to drive iteration.** After the first working version of the agent, run the eval suite. The score is your baseline. Every subsequent change should move the score up or leave it flat. If a change drops the score, you either revert it or you understand exactly why it is the right tradeoff.

**Gate deploys on evals.** An agent change that does not run evals before deploy is a bet. Some bets pay off. Most do not. Automate the eval suite as part of your CI process. A deploy that drops agent eval pass rate by more than 5% should fail automatically.

```python
def run_eval_suite(agent_fn, golden_dataset: list[dict], threshold: float = 0.90) -> dict:
    results = [run_agent_eval(agent_fn, case) for case in golden_dataset]
    pass_rate = sum(1 for r in results if r["output_correct"]) / len(results)

    return {
        "pass_rate": pass_rate,
        "passed": pass_rate >= threshold,
        "failures": [r for r in results if not r["output_correct"]],
        "total": len(results),
    }
```

The threshold is a product decision, not a technical one. 90% pass rate on 200 golden examples means 20 known failure modes you are accepting. Is that acceptable for your system? That answer belongs to the people responsible for the system, not to the engineer running the eval.

---

## LLM-as-Judge

When correctness cannot be determined by string matching or schema validation, you need a judge: a second LLM that evaluates the quality of the first LLM's output.

The judge is a Conditional Agent. It has its own context boundary, its own system prompt, and its own output schema. It runs after the fact and does not affect the primary agent's behavior.

See [LLM-as-Judge](./llm-as-judge.md) for the full treatment: rubric design, bias mitigation, panel judges, trajectory evaluation, and how to write evals for the judge itself.

---

## Connecting evals to observability

Every eval should be anchored to a trace. A failing eval without a trace is a score you cannot act on. A failing eval with a trace tells you exactly what the Model received, what tools it called, and where the reasoning went wrong.

The workflow:

```
1. Run agent       -> Harness captures full trace (prompts, tool calls, outputs)
2. Run eval        -> Score attached to trace ID
3. Eval fails      -> Open trace -> inspect what the Model actually saw
4. Diagnose        -> Is the context wrong? (HDD) or is the reasoning wrong? (LLMDD)
5. Fix and re-run  -> Score improves
```

An eval suite without traces is a collection of red and green lights with no explanation. Instrument your Harness to capture traces from the start. Retroactively adding tracing to an existing agent is harder than it sounds.

See [Observability in ADD](../observability/README.md).

---

## At a glance

| Question | Answer |
|---|---|
| What level of eval to run first? | Agent eval. It catches the most failures for the least complexity. |
| How big does the golden set need to be? | 50 to start, 200 for reliable regression signal. |
| Output eval or trajectory eval? | Start with output. Add trajectory for high-stakes behaviors. |
| When to write evals? | Before or during development, not after. |
| What to do when a production failure occurs? | Fix it, then add a regression test case. Every time. |
| How to know if evals are worth trusting? | Measure correlation between eval scores and production outcomes. |
