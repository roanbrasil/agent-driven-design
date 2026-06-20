# Human-in-the-Loop Agent — Manual Implementation [ADVANCED]

Inserts a human approval checkpoint before executing high-risk tool calls.
The Model proposes actions; the Harness gates them by risk tier before execution.

## ADD mapping

- **Model** — reasons about what actions to take, proposes tool calls
- **Harness** — risk classifier, approval gate, execution (post-approval only), loop control
- **Infra** — Anthropic API, stdin (human channel)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python agent.py
```

## Risk tiers

| Tier   | Example tools              | Gate behavior                        |
|--------|----------------------------|--------------------------------------|
| LOW    | `read_file`, `list_dir`    | Auto-approved, no human prompt       |
| MEDIUM | `write_file`, `send_email` | y/n confirmation                     |
| HIGH   | `delete_file`              | Must type the tool name to confirm   |

## What it demonstrates

- HITL approval gate as a Harness responsibility (Model is unaware)
- Risk-tiered policy: different confirmation flows per risk level
- The Model only sees the tool result — never the approval interaction
- How to reject a tool call and pass the rejection back to the Model
- Agentic loop continues normally after approval/rejection
