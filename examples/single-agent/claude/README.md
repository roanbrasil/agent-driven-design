# Single Agent — Anthropic Claude

Minimal runnable agent using the Anthropic SDK directly. No framework.

## ADD mapping

- **Model** — `claude-sonnet-4-6`: handles reasoning, decides when to call tools
- **Harness** — `agent.py`: tool definitions, tool execution, loop control, message history
- **Infra** — Anthropic API

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY
python agent.py
```

## What it demonstrates

- How the Harness constructs and maintains message history
- How tool definitions live in the Harness, not the Model
- How the agentic loop (while True) is a Harness responsibility
- How stopping conditions are handled in code, not in the prompt
