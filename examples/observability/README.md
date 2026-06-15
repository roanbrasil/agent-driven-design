# Observability Examples

Tracing is a **Harness responsibility** in ADD. The Model has no awareness of being observed. Every span, trace, and metric is instrumented in the Harness layer.

## Comparison

| Tool | Type | Backend | Best for |
|---|---|---|---|
| **Langfuse** | LLM-native | Cloud or self-hosted | Production LLM tracing, prompt versioning, human eval |
| **LangSmith** | LangChain-native | Cloud | Teams already on LangChain/LangGraph, dataset-driven evals |
| **Phoenix** | Local-first | localhost:6006 | Development, debugging, offline evals, RAG debugging |
| **OpenTelemetry** | OTel standard | Any OTel backend | Portability, existing OTel infra, Jaeger/Grafana/Datadog |

## What to trace

Every Harness step should produce a span. Minimum viable trace:

```
agent.run                    ← top-level trace (one per invocation)
  ├── llm.call               ← every Model call (with token counts)
  │     └── input/output     ← full prompt + response
  └── tool.{name}            ← every tool execution
        └── input/output     ← tool args + result
```

## What to capture per span

| Attribute | Why |
|---|---|
| `input.value` | What was sent to the Model |
| `output.value` | What the Model returned |
| `gen_ai.usage.input_tokens` | Cost tracking |
| `gen_ai.usage.output_tokens` | Cost tracking |
| `gen_ai.request.model` | Model version tracking |
| `tool.name` / `tool.input` / `tool.output` | Tool call audit |
| `agent.type` / tags | Filtering in dashboard |

## ADD connection

```
             ADD Layer
┌─────────────────────────────────┐
│  Harness                        │
│  ┌──────────────────────────┐   │
│  │  @observe / @traceable   │   │   ← instrumentation lives here
│  │  tracer.start_as_span()  │   │
│  └──────────────────────────┘   │
│                │                │
│          ┌─────▼──────┐         │
│          │   Model    │         │   ← completely unaware of tracing
│          └────────────┘         │
└─────────────────────────────────┘
```

## Quick start

```bash
# Langfuse (cloud)
cd langfuse && pip install -r requirements.txt && python agent.py

# Phoenix (local, no account)
cd phoenix && pip install -r requirements.txt && python agent.py

# OTel to stdout (zero setup)
cd opentelemetry && pip install -r requirements.txt
OTEL_BACKEND=stdout python agent.py
```
