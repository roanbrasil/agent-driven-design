# Memory Patterns

How agents store and retrieve information across turns and sessions — and where that logic belongs in the ADD layer model.

## The core principle

Memory is a Harness pattern. The Model does not maintain state — it has no persistent storage, no access to prior conversations unless the Harness provides it, and no awareness of what happened in past sessions. All memory access is mediated by the Harness.

The GLOSSARY defines three memory types. This document expands each with design guidance.

---

## Memory type 1: Working memory

Short-term, scoped to a single task or session. The conversation history (the `messages` array) is the primary working memory mechanism.

**ADD mapping:**
- What it stores: the current task state — user turns, Model turns, tool call results
- Who reads it: Model (via context window)
- Who writes it: Harness (appends each turn)
- Scope: single session

**Design guidance:**
- Working memory fills the context window — manage it actively
- Truncation, summarization, and selective retention are Harness decisions
- The Model does not decide what stays in working memory; the Harness does

**When working memory is not enough:**
- When the session context exceeds the context window
- When state must persist across sessions
- When multiple agents need access to the same state

---

## Memory type 2: Episodic memory

Records of past interactions. Stored externally, retrieved when relevant, injected into context.

```
Past session runs → stored as interaction records
    ↓
Current session starts
    ↓
Harness retrieves relevant past records
    ↓
Harness injects summary or excerpts into context
    ↓
Model reasons with historical context
```

**ADD mapping:**
- What it stores: past agent runs, user interactions, outcomes
- Who reads it: Harness (retrieves), Model (reasons over injected excerpts)
- Who writes it: Harness (records each run)
- Scope: cross-session, per user or per task type

**Design guidance:**
- Episodic memory should be retrieved selectively, not dumped wholesale
- Retrieval is a Harness decision — by recency, relevance, or explicit query
- The format injected into context should be designed for Model consumption, not storage format

---

## Memory type 3: Semantic memory

Knowledge stored as embeddings in a vector database. Retrieved by semantic similarity.

```
Documents / knowledge base → Harness embeds and stores
    ↓
User query arrives
    ↓
Harness embeds query → searches vector DB → retrieves top-k chunks
    ↓
Harness formats and injects into context
    ↓
Model reasons over retrieved knowledge
```

**ADD mapping:**
- What it stores: documents, facts, knowledge — chunked and embedded
- Who reads it: Harness (retrieves), Model (reasons over injected chunks)
- Who writes it: Harness ingestion pipeline
- Scope: shared across agents (when the same knowledge base serves multiple agents)

**Note:** This is the retrieval side of the RAG pattern. See [patterns/rag/README.md](../rag/README.md) for the full RAG treatment.

**Design guidance:**
- Chunking strategy is a Harness decision with significant impact on retrieval quality
- Retrieval quality should be evaled independently from generation quality
- If two agents share a vector DB, they share a knowledge boundary — make this explicit

---

## Memory ownership and boundaries

Memory storage is part of the Agent Context Boundary:

| Question | Implication |
|---|---|
| Who writes to this memory? | That agent or Harness owns it |
| Who reads from this memory? | All readers depend on the schema |
| Can two agents write to the same key? | Boundary violation — assign ownership |

If two agents write to the same memory for the same entity, you have a shared mutable state problem. Assign ownership: one agent writes, others read through a defined interface.

---

## Patterns for cross-session state

### User profile memory
A structured record of what the system knows about the user. Written by the Harness after each session. Read at the start of each session. Injected as a context block.

### Task checkpoint
A snapshot of in-progress task state that allows the agent to resume after interruption. Written by the Harness at each step. Read on resume. Enables long-horizon tasks.

### Shared knowledge base
A vector DB serving multiple agents. One write path (ingestion pipeline); multiple read paths (each agent's Harness queries the same store). Schema is shared and versioned.

---

## Anti-patterns

### Model-directed memory write
Having the Model decide what to remember (via a "remember_this" tool) without Harness validation. The Model's judgment about what is important is probabilistic. The Harness should have a defined policy for what gets stored.

### Prompt stuffing
Injecting large memory dumps into the context window without filtering. The Harness should select and summarize; the Model should receive focused context, not a memory dump.

### Shared write ownership
Two agents writing to the same memory location. This creates race conditions and undefined behavior when agents run in parallel. Assign ownership explicitly.
