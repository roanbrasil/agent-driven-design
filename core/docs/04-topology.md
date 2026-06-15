# 04 — Agent Topology Patterns

## What is topology?

Agent topology is the arrangement of agents in a system: how they connect, who coordinates whom, and how information flows between them. Topology is a Harness-level concern — the routing, sequencing, and coordination of agents is always code, not model reasoning.

The ADD Glossary defines four common topologies. This document expands each with design guidance and ADD-specific trade-offs.

---

## The four topologies

### 1. Pipeline

```
Input → [Agent A] → [Agent B] → [Agent C] → Output
```

Each agent processes and passes its output to the next. Sequential. Predictable. Each agent has a narrow, well-defined contract.

**When to use:**
- Tasks are naturally sequential — each step depends on the prior
- Each step has a different vocabulary or tool surface
- You want the simplest possible topology

**ADD implications:**
- Each boundary crossing requires explicit contract definition
- The Harness at each boundary is responsible for translation — not natural language passthrough
- Failure at step N halts all downstream agents unless the Harness handles it

**Anti-pattern:** chaining agents informally — passing raw text output from one agent directly into the next prompt without a defined schema. Always define the handoff object.

---

### 2. Hierarchical (Orchestrator + Workers)

```
            [Orchestrator]
           /       |       \
    [Worker A] [Worker B] [Worker C]
```

One orchestrator agent coordinates multiple worker agents. The orchestrator reasons about task decomposition and result assembly. Workers execute focused sub-tasks.

**When to use:**
- The task can be decomposed into independent sub-tasks
- The decomposition itself requires reasoning (if it doesn't, use a deterministic router instead)
- Different sub-tasks require different tool surfaces or domain vocabularies

**ADD implications:**
- The Orchestrator is a Universal Agent — its failure halts the system
- Workers are Conditional Agents — they enhance but do not load-bear
- The Orchestrator should not do domain work — it reasons about coordination, not content
- Worker results should be assembled by the Harness, not by having the Orchestrator "read" them informally

**Anti-pattern:** the Orchestrator doing analysis or generation on top of aggregating worker results. If it's producing domain content, it's also a Worker, and that's a boundary problem.

---

### 3. Peer Network

```
[Agent A] ←→ [Agent B]
     ↕               ↕
[Agent C] ←→ [Agent D]
```

Agents communicate as peers, passing work based on capability rather than hierarchy. Often event-driven. No single coordinator.

**When to use:**
- Tasks are dynamic and routing cannot be predetermined
- Agents need to collaborate without a fixed sequence
- Different parts of the work surface at different times

**ADD implications:**
- All agent-to-agent communication must go through defined contracts — never informal natural language
- Each handoff is a Domain Event; the receiving agent is not required to understand the sender's internal vocabulary
- Debugging and observability are significantly harder than in pipeline or hierarchical topologies

**When NOT to use:**
- When routing criteria are structural (use deterministic code)
- When you want predictable failure behavior
- When latency is a concern (peer coordination adds round-trip overhead)

---

### 4. Specialist Pool

```
             [Router]
            /    |    \
  [Billing] [Search] [Support]
```

Multiple specialist agents, each scoped to a domain. A router directs incoming tasks to the appropriate specialist.

**When to use:**
- Clear domain boundaries exist and routing criteria are well-defined
- Different domains require meaningfully different tool surfaces or vocabularies
- Domains are independent — a request belongs to exactly one at a time

**ADD implications:**
- The Router should be deterministic code whenever routing criteria are structural (request type, field presence, topic classification)
- If the Router is an LLM, it is a Universal Agent — make it reliable
- Each specialist has a strict context boundary — the billing agent should not have access to support tools

**Anti-pattern:** using an LLM router to decide between specialists when a simple if-else or classification function would work. Probabilistic routing adds failure modes and latency for no benefit.

---

## Choosing a topology

| Signal | Consider |
|---|---|
| Tasks are sequential and each step depends on the prior | Pipeline |
| Task decomposition requires reasoning | Hierarchical |
| Tasks are dynamic and unstructured | Peer network (use sparingly) |
| Multiple distinct domains, clear routing criteria | Specialist pool |
| Unsure | Start with a single agent. Add topology only when needed. |

---

## Topology and observability

Every topology requires different observability instrumentation:

- **Pipeline** — trace the full chain; each agent's output is the next agent's input
- **Hierarchical** — trace the orchestrator's decisions separately from worker outputs
- **Peer network** — distributed tracing; correlation IDs propagate through every handoff
- **Specialist pool** — trace routing decisions separately from specialist execution

See [production/observability/README.md](../../production/observability/README.md).

---

## Topology is a Harness decision

Agents do not know what topology they are in. An orchestrator knows it can delegate; a worker does not know it is one. Topology is entirely constructed and controlled by the Harness. This means:

- You can change topology without changing any agent's system prompt
- Routing logic belongs in code, not in natural language instructions to the Model
- A well-bounded agent is topology-agnostic — it can be used in a pipeline, a pool, or as a standalone agent without modification

---

**Back to:** [03 — Decomposition](./03-decomposition.md)
