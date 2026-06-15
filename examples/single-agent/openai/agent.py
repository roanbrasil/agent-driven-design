"""
Single Agent — OpenAI
======================
ADD mapping:
  - Model   : gpt-4o via OpenAI SDK
  - Harness : tool definitions, tool execution, loop control
  - Infra   : OpenAI API

Same pattern as the Claude example — different SDK, same ADD structure.
Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import json
import os
from openai import OpenAI

# ── Infra ─────────────────────────────────────────────────────────────────────
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ── Harness: tool definitions ─────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a mathematical expression.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
                "required": ["expression"],
            },
        },
    },
]

# ── Harness: tool execution ───────────────────────────────────────────────────
def execute_tool(name: str, arguments: str) -> str:
    inputs = json.loads(arguments)
    if name == "get_weather":
        return json.dumps({"city": inputs["city"], "temperature": "22°C", "condition": "sunny"})
    if name == "calculate":
        try:
            result = eval(inputs["expression"], {"__builtins__": {}})  # noqa: S307
            return str(result)
        except Exception as e:
            return f"Error: {e}"
    return f"Unknown tool: {name}"


# ── Harness: agentic loop ─────────────────────────────────────────────────────
def run_agent(user_message: str) -> str:
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Use tools when needed. Be concise.",
        },
        {"role": "user", "content": user_message},
    ]

    while True:
        # ADD: Model reasons given the context the Harness constructed
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # ADD: Harness interprets stop reason and decides next step
        if finish_reason == "stop":
            return message.content or ""

        if finish_reason == "tool_calls":
            messages.append(message)
            for tool_call in message.tool_calls:
                result = execute_tool(tool_call.function.name, tool_call.function.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
            continue

        return f"Unexpected finish reason: {finish_reason}"


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
