# 01 — Foundations: Model, Harness, and the Decision Rule

## The Fundamental Split

Every LLM-based agent has two distinct parts. Conflating them is the most common source of architectural problems in agentic systems.

---

### Model

The Model is the LLM. Its job is to reason.

More precisely, the Model:

- Interprets what it receives in its context window
- Applies language understanding, world knowledge, and in-context reasoning
- Produces outputs: text, structured data, tool call requests
- Makes decisions that require judgment — ambiguity resolution, intent interpretation, generation under constraints

The Model has no awareness of the system around it except through what the Harness chooses to show it. It cannot call tools directly. It cannot access memory. It cannot route to another agent. It can only produce an output and wait.

**The Model is not responsible for:**
- Knowing which tools exist (unless told)
- Deciding which agent to call next (unless that decision is itself a reasoning task)
- Validating its own outputs structurally
- Managing retries or fallbacks

---

### Harness

The Harness is all the code that surrounds and drives the Model.

The Harness:

- Constructs the context window (system prompt, retrieved memory, conversation history, tool results)
- Defines and executes tools on the Model's behalf
- Parses and validates Model outputs
- Decides what happens next (retry, route, escalate, return)
- Manages state across turns
- Handles observability, tracing, and error handling
- Enforces constraints the Model cannot enforce on itself

The Harness is deterministic code. It does not reason about domain problems. It controls the conditions under which reasoning happens.

**The Harness is not responsible for:**
- Solving problems that require language or judgment
- Substituting for Model capability with increasingly complex prompt engineering
- Encoding business logic that belongs in domain services

---

## The Decision Rule

When you are designing an agent and encounter a piece of logic, ask:

```
Does this require reasoning, language understanding, or judgment?
  → Model

Is this structure, control flow, contract enforcement, or data transformation?
  → Harness

Does this serve the Harness with storage, compute, network, or I/O?
  → Infra
```

This rule is not always clean. Some cases require both — for example, output validation where you want both structural checking (Harness) and semantic checking (Model). That's fine. The point is to make the split explicit, not to avoid overlap.

---

## Common Misalignments

### Logic that belongs in the Harness but lives in the Model

**Symptom:** Prompt contains routing instructions, retry conditions, or structural validation rules written in natural language.

**Problem:** Natural language instructions are interpreted probabilistically. Routing in the prompt will occasionally be wrong. Structural validation in the prompt will occasionally be ignored. This logic belongs in code.

**Fix:** Move control flow to the Harness. The Model should receive a context that makes the right action obvious, not a context that contains the rules for deciding what to do.

---

### Logic that belongs in the Model but lives in the Harness

**Symptom:** Harness contains large if-else trees that try to enumerate domain cases. Harness prompt templates grow to hundreds of lines trying to anticipate every scenario.

**Problem:** You are encoding reasoning in code that should be done by the Model. The Harness becomes brittle and hard to maintain.

**Fix:** Trust the Model with domain reasoning. Give it the right context and a well-defined output schema. Let it reason; parse the result in the Harness.

---

### Infra concerns bleeding into the Harness

**Symptom:** Harness code mixes retry logic, database calls, HTTP clients, and orchestration in the same function.

**Problem:** The Harness becomes untestable and hard to reason about.

**Fix:** The Harness depends on infra through interfaces. Storage, retrieval, and execution are injected; the Harness orchestrates them without implementing them.

---

## Practical Test

For any piece of logic you're building, ask:

> "If I replaced the Model with a different model (different provider, different size, different version), would this logic change?"

- If yes → it belongs in the Harness or closer to the Model boundary
- If no → it's either Harness logic (stable regardless of model) or Infra

And the inverse:

> "If I rewrote the Harness from scratch (different framework, different language), would the Model behavior need to change?"

- If yes → the Model is doing work that belongs in the Harness
- If no → the separation is clean

---

## Summary

| | Model | Harness |
|---|---|---|
| **Nature** | Probabilistic | Deterministic |
| **Responsibility** | Reasoning, generation, judgment | Control, structure, execution |
| **Fails when** | Context is incomplete or misleading | Domain logic leaks in |
| **Tests look like** | Evals, behavioral assertions | Unit tests, integration tests |
| **Versioned by** | Model card / provider | Code repository |

An agent is the combination of both. Neither is complete without the other. Designing an agent well means knowing, for every decision in the system, which side of this line it belongs on — and being explicit about why.

---

**Next:** [02 — Agent Context Boundaries](./02-boundaries.md)
