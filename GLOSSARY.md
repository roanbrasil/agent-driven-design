# Glossary

Core vocabulary for Agent-Driven Design. Where a concept maps to an existing DDD term, the mapping is noted — but the ADD definition stands on its own.

---

## Agent

The fundamental unit of composition in ADD. An agent is always `Model + Harness`. Neither part alone constitutes an agent.

---

## Model

The LLM inside an agent. Responsible for reasoning, language understanding, generation, and judgment. Operates exclusively within its context window. Has no direct access to tools, memory, or other agents — only what the Harness provides.

---

## Harness

All the code surrounding the Model. Responsible for constructing context, defining and executing tools, parsing outputs, managing state, routing, and observability. Does not reason about domain problems. Does not substitute for Model capability.

---

## Agent Context Boundary

The conceptual limit of what an agent knows, can do, and owns. Within the boundary, vocabulary and tools have precise meaning. Crossing the boundary requires explicit translation.

*DDD analog: Bounded Context*

---

## Agent Contract

The formal interface of an agent: the input schema it accepts and the output schema it produces. Defined and maintained by the Harness. Versioned independently of the Model.

*DDD analog: Ubiquitous Language — the shared vocabulary made explicit at the boundary*

---

## Agent Topology

The arrangement of agents in a system: how they connect, who orchestrates whom, and how information flows. Common topologies include pipeline, hierarchical, peer network, and specialist pool.

*DDD analog: Context Map*

---

## Context Translation

The deliberate process of converting data or instructions from one agent's vocabulary into another's. Always the Harness's responsibility. Never done implicitly or through natural language alone.

*DDD analog: Anti-Corruption Layer*

---

## Tool

A capability made available to the Model by the Harness. The Model requests tool execution; the Harness executes it. The Model never executes tools directly.

*DDD analog: Domain Service*

---

## Memory Store

Persistent or session-scoped storage that the Harness reads from and writes to on behalf of the Model. Types include episodic (interaction history), semantic (embeddings / vector retrieval), and working (short-term, scoped to a task).

*DDD analog: Repository*

---

## Orchestrator

An agent whose primary responsibility is coordinating other agents: decomposing tasks, routing work, and assembling results. Does not do domain work itself.

---

## Worker

An agent that executes a focused sub-task delegated by an Orchestrator. Has a narrow context boundary and a well-defined contract.

---

## Agent Cluster

A group of agents that together fulfill a coherent capability — typically one Orchestrator and its Workers. Treated as a unit from outside the cluster.

*DDD analog: Aggregate*

---

## Handoff

The act of one agent completing its work and passing control or data to another. A handoff crosses an Agent Context Boundary and must go through a defined contract, not informal natural language.

*DDD analog: Domain Event*

---

## Universal Agent

An agent that participates in every execution path. Load-bearing. Removing it causes system failure. Requires high reliability design in the Harness (retries, fallbacks, circuit breakers).

---

## Conditional Agent

An agent activated by context, not always in the execution path. Enhancement rather than load-bearing. Can fail without breaking the system; failure degrades quality, not availability.

---

## Attention Dilution

Degradation in Model output quality caused by a context window that contains too much irrelevant or loosely related information. A primary motivation for Agent Context Boundaries and focused tool surfaces.

---

## Prompt Schema

The structured template the Harness uses to construct the Model's context. Part of the Agent Contract. Changes to the prompt schema are versioned changes to the agent's interface.

---

## Infra

Everything that serves the Harness without reasoning about domain problems. Includes vector databases, queues, execution environments, HTTP clients, and logging infrastructure. The Harness depends on Infra through interfaces; Infra does not contain agent logic.

---

## God Agent

Anti-pattern. A single agent with an unbounded context, a large mixed tool surface, and multiple unrelated objectives. The agentic equivalent of a god class. Symptoms: long system prompts with conditional sections, mixed tool domains, difficulty writing evals.

---

## Harness-Driven Design (HDD)

A design strategy where improvements to an agent are made by changing the Harness — prompts, tools, context construction, routing, memory — while keeping the Model constant. HDD is the default approach: most agent failures are Harness failures, and Harness changes are faster, cheaper, and more reversible than Model changes.

*See: [HDD vs LDD](guides/hdd-vs-ldd.md)*

---

## LLM-Driven Design (LDD)

A design strategy where improvements to an agent are made by changing the Model — selecting a better base model or fine-tuning — while keeping the Harness constant. LDD is applied only after HDD has been exhausted and evals confirm the failure is in the Model's reasoning, not in the context it receives.

*See: [HDD vs LDD](guides/hdd-vs-ldd.md)*
