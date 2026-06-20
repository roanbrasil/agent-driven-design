# Single Agent with Memory — Anthropic [INTERMEDIATE]

Conversational agent that extracts and stores facts across turns.
Demonstrates that **the Model is stateless — memory is a Harness responsibility**.

## ADD mapping

- **Model** — answers questions, extracts facts on demand
- **Harness** — `memory` dict (long-term), `conversation` list (short-term), fact injection, extraction trigger
- **Infra** — Anthropic API

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python agent.py
```

## What it demonstrates

- Short-term memory: conversation history passed in every call
- Long-term memory: a dict updated by a dedicated extractor Model call
- Fact injection: the Harness builds the system prompt dynamically with known facts
- Memory is purely a Harness construct — the Model doesn't "store" anything
