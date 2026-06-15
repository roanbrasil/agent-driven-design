# 03 — Decomposition: When and How to Split into Multiple Agents

## The Default Position

A single well-designed agent is almost always preferable to multiple poorly-bounded ones. Decomposition adds coordination overhead, failure surfaces, and operational complexity. The burden of proof is on decomposition.

Start with one agent. Decompose only when you can name the specific problem it solves.

---

## Valid Reasons to Decompose

### 1. Context overflow

The problem reliably requires more information than fits in one context window without degrading reasoning quality. This is the most concrete trigger — it's measurable.

Signs:
- Evals show quality drop when full context is injected
- You are truncating, summarizing, or selecting inputs in ways that lose important information
- The agent's effective attention is spread too thin

Response: decompose by scope. Give each agent a focused slice of the problem. Use an orchestrator to assemble results.

---

### 2. Domain separation

Two parts of the system use different vocabularies, tools, or objectives that would pollute each other in a shared context.

Signs:
- The system prompt contains conditional sections: "when doing X, use these rules; when doing Y, use these other rules"
- Tool lists are large and unrelated
- The agent's correct behavior depends heavily on which "mode" it's in

Response: decompose by domain. Each agent gets its own boundary, vocabulary, and tool surface.

---

### 3. Parallelism

Work is genuinely independent and latency matters. Two sub-tasks that do not depend on each other's outputs can be executed simultaneously by separate agents.

Signs:
- Sequential execution of independent tasks creates unnecessary latency
- Sub-tasks produce outputs that are later merged, not chained

Response: decompose into parallel workers with a collector. The orchestrator fans out and collects; it does not need to be an LLM.

---

### 4. Fault isolation

Failure in one area must not cascade. A failure in a non-critical agent should degrade gracefully, not bring down the entire system.

Signs:
- A single agent handles both critical-path and non-critical reasoning
- One failure mode causes total loss of output
- Different parts of the system have different reliability requirements

Response: decompose by criticality. Isolate the high-reliability path. Let non-critical agents fail without affecting it.

---

### 5. Specialization

A focused agent measurably outperforms a general one on a specific task.

This is the weakest reason to decompose — measure it before acting on it. Specialization gains are real but often smaller than expected, and the coordination cost is real and often larger than expected.

Signs:
- Eval data shows a focused prompt on a subset of the task consistently outperforms the general prompt
- The task is well-defined enough that a specialized agent is stable and maintainable

Response: decompose only after measuring. A specialized system prompt within a single agent may be sufficient.

---

## The Decomposition Decision

Before splitting an agent, answer these questions:

1. **What specific problem does decomposition solve?**
   If you cannot name it precisely, don't decompose.

2. **What does coordination cost?**
   Each agent boundary adds latency, a failure point, a contract to maintain, and observability to instrument.

3. **Can the Harness solve it instead?**
   Routing, retrieval scoping, and tool gating in the Harness can often address boundary problems without creating new agents.

4. **What is the agent topology?**
   Decomposition implies a topology. Name it before building it. (See [04 — Topology](./04-topology.md))

---

## Decomposition Patterns

### Pipeline

Each agent processes and passes to the next. Output of one is input to the next. Simple, sequential, predictable.

```
Input → [Agent A] → [Agent B] → [Agent C] → Output
```

Use when: tasks are naturally sequential and each step depends on the prior.

---

### Hierarchical (Orchestrator + Workers)

One orchestrator agent coordinates multiple worker agents. The orchestrator reasons about task decomposition and result assembly. Workers execute focused sub-tasks.

```
            [Orchestrator]
           /       |       \
    [Worker A] [Worker B] [Worker C]
```

Use when: a complex task can be decomposed into independent sub-tasks, and the decomposition itself requires reasoning.

---

### Peer Network

Agents communicate as peers, passing work based on capability rather than hierarchy. Often event-driven.

```
[Agent A] ←→ [Agent B]
     ↕               ↕
[Agent C] ←→ [Agent D]
```

Use when: tasks are dynamic and routing decisions cannot be predetermined. Adds significant coordination complexity — use sparingly.

---

### Specialist Pool

Multiple specialist agents, each scoped to a domain. A router (which may or may not be an LLM) directs incoming tasks to the appropriate specialist.

```
             [Router]
            /    |    \
  [Billing] [Search] [Support]
```

Use when: clear domain boundaries exist and routing criteria are well-defined. The router can be deterministic code if routing criteria are structural.

---

## Universal vs. Conditional Agents

Research on multi-agent systems identifies a useful distinction:

**Universal agents** — present in every execution path. Removing them causes the system to fail catastrophically. These are load-bearing; design them with high reliability requirements.

**Conditional agents** — activated by context, not always in the path. Removing them degrades quality but does not break the system. These are enhancement; they can fail more gracefully.

Know which category each agent in your topology falls into. Universal agents get more defensive Harness design (retries, fallbacks, circuit breakers). Conditional agents can fail softer.

---

## Anti-Patterns

### Premature decomposition
Splitting a single agent that works into multiple agents before any concrete problem with the single-agent design has been identified. Creates coordination complexity for no benefit.

### Coordination through the Model
Using an LLM as the router in a topology where routing criteria are structural (e.g., "if the request contains a booking ID, route to booking agent"). Routing on structural criteria belongs in the Harness.

### Agents as microservices
Treating every function or capability as a separate agent. The grain is too fine. An agent should have a coherent objective, not a single function.

### Topology without contracts
Decomposing into multiple agents without defining the handoff schema between them. Each agent's output becomes another's informal input. This is technical debt that compounds quickly.

---

**Next:** [04 — Agent Topology Patterns](./04-topology.md)
