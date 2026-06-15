# Evals in ADD

## The three levels of evaluation

ADD distinguishes three distinct evaluation targets. Conflating them is a common mistake.

### 1. Model eval
Tests the Model in isolation — given a fixed input, does it produce the right output?

- No tools, no Harness context
- Useful for: model selection, regression testing after model upgrades
- Limitation: does not reflect real agent behavior (the Model never runs in isolation)

### 2. Agent eval
Tests the full Agent (Model + Harness) — given a user task, does the agent produce the right final output?

- Runs the full loop including tool calls and memory
- Most representative of production behavior
- Useful for: detecting Harness regressions, prompt changes, tool changes

### 3. System eval
Tests a multi-agent topology — given an end-to-end task, does the system produce the right result?

- Multiple agents, full topology
- Most expensive to run; most representative of real usage
- Useful for: detecting inter-agent contract violations, boundary leaks

## The eval decision rule

> "Did the Model reason correctly given the context it received?"
> → Model eval (fix: better base model, fine-tuning)
>
> "Did the agent produce the right answer given the user task?"
> → Agent eval (fix: Harness — better prompt, better tools, better retrieval)
>
> "Did the system produce the right end result?"
> → System eval (fix: topology, contracts, routing)

## What makes a good eval

For agentic systems, output-only evals are often insufficient. A good eval captures:

- **Correctness** — is the final output right?
- **Trajectory** — did the agent take the right steps?
- **Efficiency** — did the agent use unnecessary tool calls or loop iterations?
- **Boundary adherence** — did each agent stay within its context boundary?

## LLM-as-Judge in ADD

LLM-as-Judge evals (using a Model to score another Model's output) are a Harness pattern. The judge is a separate agent with its own context boundary — it receives the task, the output, and a scoring rubric, and produces a score.

The judge is a conditional agent: it runs after the fact, does not affect the primary agent's behavior, and can fail without breaking the system.

## Connecting to observability

Every eval should be attached to a trace. The trace provides the full context (what prompt was sent, what tools were called) that makes a failing eval debuggable.

Workflow:
1. Run agent → trace captured by Harness
2. Eval runs against the trace output
3. Failing eval → open trace → identify whether failure is in Model or Harness
4. Fix → re-run → score improves

See [production/observability/README.md](../observability/README.md).
