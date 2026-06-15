"""
Observability — Arize Phoenix
==============================
Phoenix is an open-source, local-first LLM observability tool by Arize AI.
Runs entirely on your machine — no cloud account needed.
Excellent for development, debugging, and offline evals.

Key differences:
  - Fully local by default (localhost:6006)
  - Strong eval library (Phoenix Evals) built-in
  - OpenTelemetry-based (compatible with other OTel collectors)
  - Great for RAG pipeline debugging (retrieval traces)

ADD mapping: same as others — tracing is Harness, Model is unaware.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
    # Open http://localhost:6006 to see traces
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()

# ── Infra: Phoenix setup ──────────────────────────────────────────────────────
import phoenix as px
from phoenix.otel import register
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Launch Phoenix UI (opens http://localhost:6006)
session = px.launch_app()

# Register OTel tracer pointing to Phoenix
tracer_provider = register(
    project_name="add-examples",
    endpoint="http://localhost:6006/v1/traces",
)
tracer = trace.get_tracer(__name__)

from anthropic import Anthropic
anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── Harness: tools ────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
    {
        "name": "calculate",
        "description": "Evaluate a math expression.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
]

def execute_tool(name: str, inputs: dict) -> str:
    # ADD: tool execution is Harness; Phoenix traces it via OTel spans
    with tracer.start_as_current_span(f"tool.{name}") as span:
        span.set_attribute("tool.name", name)
        span.set_attribute("tool.inputs", json.dumps(inputs))
        if name == "get_weather":
            result = json.dumps({"city": inputs["city"], "temperature": "22°C", "condition": "sunny"})
        elif name == "calculate":
            try:
                result = str(eval(inputs["expression"], {"__builtins__": {}}))  # noqa: S307
            except Exception as e:
                result = f"Error: {e}"
        else:
            result = f"Unknown tool: {name}"
        span.set_attribute("tool.output", result)
        return result


# ── Harness: agentic loop with OTel tracing ────────────────────────────────────
def run_agent(user_message: str) -> str:
    """ADD: OTel spans are Harness instrumentation. Model is unaware."""
    with tracer.start_as_current_span("agent.run") as root_span:
        root_span.set_attribute("input.value", user_message)
        root_span.set_attribute("agent.type", "single-agent")

        system = "You are a helpful assistant. Use tools when needed. Be concise."
        messages = [{"role": "user", "content": user_message}]
        step = 0

        while True:
            step += 1
            with tracer.start_as_current_span(f"llm.call.step{step}") as llm_span:
                llm_span.set_attribute("llm.model", "claude-sonnet-4-6")
                llm_span.set_attribute("llm.step", step)

                response = anthropic_client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=system,
                    tools=TOOLS,
                    messages=messages,
                )

                llm_span.set_attribute("llm.stop_reason", response.stop_reason)
                llm_span.set_attribute("llm.input_tokens", response.usage.input_tokens)
                llm_span.set_attribute("llm.output_tokens", response.usage.output_tokens)

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        root_span.set_attribute("output.value", block.text)
                        root_span.set_status(Status(StatusCode.OK))
                        return block.text
                return ""

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue

            root_span.set_status(Status(StatusCode.ERROR, f"Unexpected stop: {response.stop_reason}"))
            return f"Unexpected stop reason: {response.stop_reason}"


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    queries = [
        "What's the weather in Tokyo?",
        "What is 1234 * 5678?",
    ]
    for q in queries:
        print(f"\n> {q}")
        print(run_agent(q))

    print(f"\nOpen Phoenix UI: {session.url}")
    input("Press Enter to exit (keeps Phoenix running)...")
