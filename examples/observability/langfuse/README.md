# Observability — Langfuse

**Langfuse** is an open-source LLM observability platform. Self-hostable or cloud.

## What you get

- **Traces** — one per `run_agent()` call, with input/output
- **Spans** — one per `call_model()` and `execute_tool()` call
- **Token usage** — input/output tokens per LLM call, cost tracking
- **Scores** — attach human or automated eval scores to traces
- **Prompt management** — version and A/B test prompts (optional)

## ADD connection

Tracing is a Harness responsibility. `@observe` decorators sit in the Harness, never inside Model calls. The Model is completely unaware it is being traced.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

**Option A — Langfuse Cloud (easiest):**
1. Create account at https://cloud.langfuse.com
2. Get API keys from Settings → API Keys
3. Add to `.env`

**Option B — Self-hosted:**
```bash
git clone https://github.com/langfuse/langfuse
cd langfuse
docker compose up
```
Then set `LANGFUSE_HOST=http://localhost:3000`

```bash
python agent.py
```

Open your Langfuse dashboard to see traces.
