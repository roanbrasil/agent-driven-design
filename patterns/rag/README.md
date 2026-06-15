# RAG as a Harness Pattern

## The ADD view of RAG

Retrieval-Augmented Generation is not a Model capability — it is a Harness pattern.

The Model does not retrieve. The Model does not know a vector database exists. The Model only reasons about what the Harness puts into its context window.

```
User query
    │
    ▼
[Harness: embed query]           ← Infra: embedding model
    │
    ▼
[Harness: search vector DB]      ← Infra: vector database
    │
    ▼
[Harness: select + format chunks]  ← Harness: retrieval strategy
    │
    ▼
[Harness: inject into context]   ← Harness: prompt construction
    │
    ▼
[Model: reason over retrieved context]  ← Model: generation
    │
    ▼
[Harness: parse + return output] ← Harness: output handling
```

## Harness responsibilities in RAG

- **Chunking strategy** — how documents are split (size, overlap, semantic boundaries)
- **Embedding** — which embedding model, which vector DB
- **Retrieval strategy** — top-k, MMR, hybrid search, reranking
- **Context selection** — which retrieved chunks are actually injected
- **Prompt construction** — how retrieved context is formatted and positioned
- **Citation tracking** — mapping output claims back to source chunks
- **Cache** — whether repeated queries reuse retrieval results

## Model responsibilities in RAG

- Reasoning over the retrieved context
- Deciding whether the retrieved context is sufficient to answer
- Synthesizing an answer from multiple retrieved chunks
- Identifying when retrieved context is irrelevant or contradictory

## Common mistakes

**Mistake: treating retrieval as a tool call**
Making retrieval a tool the Model calls gives the Model control over what it knows. This is appropriate for agentic RAG (where the Model decides when to retrieve), but not for basic RAG where retrieval should always happen.

**Mistake: injecting too many chunks**
More retrieved context is not always better. It increases token usage and can dilute the Model's focus. The Harness should select and rank, not just dump.

**Mistake: no retrieval quality eval**
The retrieval step can fail silently — the correct documents exist but are not retrieved. Eval the retrieval step separately from the generation step.

## Agentic RAG

In agentic RAG, retrieval becomes a tool the Model can call. This is appropriate when:
- The query requires multiple, targeted retrievals
- The Model needs to decide whether to retrieve at all
- Different sub-questions require retrieval from different sources

In agentic RAG, the tool call is still Harness execution — the Model requests retrieval, the Harness executes it.
