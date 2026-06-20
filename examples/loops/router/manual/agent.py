"""
Router Agent — Manual Implementation (Anthropic)  [INTERMEDIATE]
================================================================
The Router pattern classifies incoming requests and dispatches them to
specialized handlers. The Model acts as the classifier; the Harness
owns the routing table, dispatch logic, and handler execution.

ADD mapping:
  - Model   : intent classification (which handler?), handler execution
  - Harness : routing table, dispatch, fallback logic, handler definitions
  - Infra   : Anthropic API

Intents handled:
  - weather     → WeatherHandler (tool-using agent)
  - math        → MathHandler (tool-using agent)
  - translation → TranslationHandler (direct Model call, no tools)
  - unknown     → FallbackHandler

Key ADD insight: the Router is a Conditional agent — it only activates
the handler the Model selects. Each handler has its own system prompt
(its own Agent Context Boundary).

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import json
import os
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


# ── Harness: classifier ───────────────────────────────────────────────────────
CLASSIFIER_SYSTEM = """You are a request classifier. Given a user message, determine
which handler should process it.

Respond with ONLY one of these words:
  weather      — questions about weather or temperature
  math         — arithmetic, calculations, or number problems
  translation  — translating text between languages
  unknown      — anything that doesn't fit the above

No explanation. Just the single word."""


def classify(message: str) -> str:
    """ADD: Model classifies intent. Harness uses the label to route."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=10,
        system=CLASSIFIER_SYSTEM,
        messages=[{"role": "user", "content": message}],
    )
    label = response.content[0].text.strip().lower()
    return label if label in ("weather", "math", "translation") else "unknown"


# ── Harness: handler tool definitions ────────────────────────────────────────
WEATHER_TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    }
]

MATH_TOOLS = [
    {
        "name": "calculate",
        "description": "Evaluate a mathematical expression.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    }
]


# ── Harness: tool execution ───────────────────────────────────────────────────
def run_weather_tool(name: str, inputs: dict) -> str:
    if name == "get_weather":
        return json.dumps({"city": inputs["city"], "temp": "21°C", "condition": "clear"})
    return f"Unknown tool: {name}"


def run_math_tool(name: str, inputs: dict) -> str:
    if name == "calculate":
        try:
            return str(eval(inputs["expression"], {"__builtins__": {}}))  # noqa: S307
        except Exception as e:
            return f"Error: {e}"
    return f"Unknown tool: {name}"


# ── Harness: generic tool-using agent ────────────────────────────────────────
def run_tool_agent(system: str, tools: list, execute_fn, message: str) -> str:
    """ADD: Reusable agent loop. System + tools define the Agent Context Boundary."""
    messages = [{"role": "user", "content": message}]
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=system,
            tools=tools,
            messages=messages,
        )
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""
        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": execute_fn(block.name, block.input),
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": results})
        else:
            return f"Unexpected stop: {response.stop_reason}"


# ── Harness: handler definitions ──────────────────────────────────────────────
# Each handler has its own system prompt = its own Agent Context Boundary.

def handle_weather(message: str) -> str:
    return run_tool_agent(
        system="You are a weather assistant. Use the get_weather tool and give a brief, friendly answer.",
        tools=WEATHER_TOOLS,
        execute_fn=run_weather_tool,
        message=message,
    )


def handle_math(message: str) -> str:
    return run_tool_agent(
        system="You are a math assistant. Use the calculate tool to solve problems precisely.",
        tools=MATH_TOOLS,
        execute_fn=run_math_tool,
        message=message,
    )


def handle_translation(message: str) -> str:
    """ADD: No tools needed — Model translates directly. Still its own boundary."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system="You are a translation assistant. Translate the requested text accurately and return only the translation.",
        messages=[{"role": "user", "content": message}],
    )
    return response.content[0].text


def handle_unknown(message: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system="You are a helpful assistant. If you can't handle a request, explain politely.",
        messages=[{"role": "user", "content": message}],
    )
    return response.content[0].text


# ── Harness: routing table ────────────────────────────────────────────────────
ROUTER: dict[str, callable] = {
    "weather": handle_weather,
    "math": handle_math,
    "translation": handle_translation,
    "unknown": handle_unknown,
}


def route(message: str) -> str:
    """ADD: Harness classifies then dispatches. Model only sees each isolated context."""
    intent = classify(message)
    print(f"  [router → {intent}]")
    handler = ROUTER[intent]
    return handler(message)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    queries = [
        "What's the weather like in Recife today?",
        "What is 2 to the power of 10 minus 24?",
        "Translate 'good morning' to Portuguese and Japanese",
        "Write me a poem about distributed systems",
    ]
    for q in queries:
        print(f"\nUser: {q}")
        answer = route(q)
        print(f"Agent: {answer}")
