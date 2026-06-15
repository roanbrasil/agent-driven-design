# Observability in ADD

## The principle

Observability is a Harness responsibility. The Model cannot observe itself — it has no access to latency, token counts, tool call history, or system context. The Harness is the only layer with complete visibility into what happened during an agent run.

This means:
- Every trace is constructed by the Harness
- Every span corresponds to a Harness operation
- Every metric (tokens, latency, cost) is collected by the Harness
- The Model is always a black box from the outside — what goes in and what comes out is all you can observe

## What to observe

### Per agent run (trace)
- Input (user message or task)
- Final output
- Total duration
- Total token usage (input + output)
- Estimated cost
- Tags: agent type, topology, environment

### Per Model call (span)
- Full prompt (system + messages)
- Full response
- Model name and version
- Input/output tokens
- Stop reason
- Latency

### Per tool call (span)
- Tool name
- Input arguments
- Output result
- Latency
- Success/failure

### Per loop iteration (span)
- Iteration number
- State at start of iteration
- Routing decision

## Signals that matter

| Signal | What it reveals |
|---|---|
| High input token count | Context window pressure; possible boundary leak |
| Many loop iterations | Agent struggling; possible loop without progress |
| Tool call failure rate | Reliability of Harness tool execution |
| Stop reason distribution | How often the agent completes vs. hits limits |
| Output length variance | Model uncertainty (high variance = inconsistent behavior) |
| Latency per step | Where time is being spent (Model vs. tools vs. routing) |

## The three questions observability answers

1. **What did the agent do?** — reconstruct from spans
2. **Why did the agent do it?** — read the prompt that produced each decision
3. **Did the agent do it correctly?** — attach scores (evals) to traces

## Tool comparison

See [examples/observability/README.md](../../examples/observability/README.md) for runnable examples and comparison.

## Connecting to evals

Traces are the raw material for evals. A trace records what happened; an eval scores whether it was correct. In ADD terms:
- The trace is a Harness artifact
- The eval tests the Agent (Model + Harness) behavior
- A failing eval points to either a Model problem (wrong reasoning) or a Harness problem (wrong context, wrong tools)

See [production/evals/README.md](../evals/README.md).
