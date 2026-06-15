# Integration Patterns

How agents connect to external systems — and where that connection belongs in the ADD layer model.

## The core principle

Every integration is a Harness responsibility. The Model does not connect to databases, APIs, queues, or file systems. The Model requests actions; the Harness executes them. This is true whether the integration is a tool, a retrieval step, or a streaming response.

---

## Pattern 1: Tool-backed integration

The most common pattern. The Harness exposes an external system as a tool the Model can call.

```
Model requests: {"tool": "get_order", "input": {"order_id": "123"}}
    ↓
Harness executes: calls OrderService API
    ↓
Harness returns: {"status": "shipped", "eta": "2024-01-15"}
    ↓
Model reasons over the result
```

**ADD responsibilities:**
- Tool schema definition → Harness
- Tool execution → Harness
- Error handling (retry, fallback, timeout) → Harness
- Result formatting before injection into context → Harness
- Decision to call the tool → Model

**Design guidance:**
- Keep tool schemas minimal — only the fields the Model needs to make a decision
- Tools should be idempotent where possible; the Model may call them multiple times
- Return structured data, not human-readable text — the Harness can format for display; the Model needs structure for reasoning

---

## Pattern 2: Streaming integration

When the agent's output must be delivered progressively (chat UIs, long-form generation).

```
Harness starts streaming API call
    → Harness yields each token/chunk to the consumer
    → Consumer renders progressively
    → Harness detects tool call in stream, pauses, executes, resumes
```

**ADD responsibilities:**
- Streaming loop control → Harness
- Detecting tool calls within a stream → Harness
- Buffering partial tool call JSON before execution → Harness
- Delivering chunks to the consumer → Harness (or Infra)

---

## Pattern 3: Event-driven integration

The agent is triggered by an external event (a message on a queue, a webhook, a cron).

```
External system → queue/webhook → Harness trigger
    → Harness constructs agent context from event payload
    → Agent runs
    → Harness routes output to the appropriate downstream system
```

**ADD responsibilities:**
- Event consumption → Infra
- Constructing agent context from event → Harness
- Publishing agent output → Harness
- Retry and dead-letter handling → Harness / Infra

**Note:** the Model does not know it was triggered by an event. It receives a context window constructed by the Harness from the event payload.

---

## Pattern 4: Database and state integration

When the agent needs to read from or write to a persistent store.

**Read (retrieval):**
```
Harness queries DB → formats results → injects into context → Model reasons
```
The Model does not write queries. It receives curated data.

**Write (side effect):**
```
Model produces structured output
    → Harness validates output
    → Harness writes to DB
```
The Model does not execute writes. It produces the data; the Harness persists it.

**ADD principle:** state ownership is part of the Agent Context Boundary. If two agents both write to the same store for the same key, there is a boundary violation.

---

## Anti-patterns

### Direct tool access to multiple domains
An agent whose tools span unrelated external systems (billing API + support CRM + logistics tracking). This is a boundary violation. Split by domain.

### Embedding credentials in prompts
Passing API keys or auth tokens through the context window. The Model does not need credentials — the Harness handles authentication before tool execution.

### Unvalidated write-back
Taking the Model's structured output and writing it to a database without Harness-level validation. The Model's output is probabilistic. Validate before persisting.

### Tool call as primary routing
Using tool calls to route between agents when a conditional in the Harness would work. Save tool calls for when the Model genuinely needs to decide what to call based on content.
