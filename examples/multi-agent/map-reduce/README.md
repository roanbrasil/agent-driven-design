# Multi-Agent Map-Reduce — Anthropic [ADVANCED]

Fan-out topology: a Coordinator dispatches N independent Worker agents (map),
then a Reducer synthesizes all Worker outputs (reduce).

Workers run concurrently via Python threads. Each Worker is isolated —
they don't share context with each other until the Reducer sees all results.

## ADD mapping

- **Model** — Worker analysis, Reducer synthesis
- **Harness** — fan-out dispatch, concurrency, result collection, reduce trigger
- **Infra** — Anthropic API, `concurrent.futures.ThreadPoolExecutor`

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python agent.py
```

## What it demonstrates

- Map-Reduce agent topology: parallel Workers + single Reducer
- Worker isolation: each Worker only sees its own document
- Concurrent Model calls via ThreadPoolExecutor
- Reducer as a separate Agent Context Boundary that sees all results
- How to keep output deterministic when using concurrent agents
