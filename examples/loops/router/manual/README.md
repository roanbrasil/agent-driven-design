# Router Agent — Manual Implementation [INTERMEDIATE]

Classifies incoming requests and dispatches them to specialized handler agents.
Each handler has its own system prompt = its own Agent Context Boundary.

## ADD mapping

- **Model** — intent classifier, each handler's reasoning
- **Harness** — routing table, dispatch logic, handler definitions, fallback
- **Infra** — Anthropic API

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python agent.py
```

## What it demonstrates

- How to use a lightweight Model call for classification (intent → label)
- How the Harness owns the routing table (not the Model)
- How each handler is an isolated Agent Context Boundary
- Conditional agents: only the matched handler runs
- Handlers can be tool-using agents or direct Model calls
