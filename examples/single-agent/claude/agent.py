"""
Single Agent — Anthropic Claude
================================
ADD mapping:
  - Model   : claude-sonnet-4-6 via Anthropic SDK
  - Harness : everything in this file outside the API call
              (tool definitions, tool execution, loop control, output parsing)
  - Infra   : Anthropic API (network I/O)

The agent answers questions about the weather and can do math.
Run:
    pip install -r requirements.txt
    cp .env.example .env   # add your ANTHROPIC_API_KEY
    python agent.py
"""

import json
import os
from anthropic import Anthropic

# ── Infra ─────────────────────────────────────────────────────────────────────
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── Harness: tool definitions ─────────────────────────────────────────────────
# The Model receives these definitions and decides when to call them.
# Execution always happens here in the Harness, never inside the Model.

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "calculate",
        "description": "Evaluate a mathematical expression.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression, e.g. '2 + 2'"},
            },
            "required": ["expression"],
        },
    },
]


# ── Harness: tool execution ───────────────────────────────────────────────────
# The Model requests a tool call. The Harness executes it and returns the result.

def execute_tool(name: str, inputs: dict) -> str:
    if name == "get_weather":
        # Stub — replace with a real weather API call
        return json.dumps({"city": inputs["city"], "temperature": "22°C", "condition": "sunny"})
    if name == "calculate":
        try:
            result = eval(inputs["expression"], {"__builtins__": {}})  # noqa: S307
            return str(result)
        except Exception as e:
            return f"Error: {e}"
    return f"Unknown tool: {name}"


# ── Harness: agentic loop ─────────────────────────────────────────────────────
# The loop drives the Model until it produces a final text response.
# Stopping condition, retry logic, and routing all belong here.

def run_agent(user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]

    # ADD: system prompt is Harness — it defines the Model's context and constraints
    system = (
        "You are a helpful assistant. "
        "Use tools when you need current data or precise calculation. "
        "Be concise."
    )

    while True:
        # ADD: this is the Model doing its job — reasoning given the context
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # ADD: Harness inspects the stop reason and decides what happens next
        if response.stop_reason == "end_turn":
            # Model is done — extract final text
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        if response.stop_reason == "tool_use":
            # Model requested tool calls — Harness executes them
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Append Model turn + tool results to history, then loop
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason — Harness handles gracefully
        return f"Unexpected stop reason: {response.stop_reason}"


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    queries = [
        "What's the weather in Tokyo?",
        "What is 1234 * 5678?",
        "What's the weather in Paris and how much is 100 * 1.2?",
    ]
    for q in queries:
        print(f"\n> {q}")
        print(run_agent(q))
