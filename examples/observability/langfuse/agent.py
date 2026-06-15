"""
Observability — Langfuse
=========================
Langfuse is an open-source LLM observability platform.
Self-hostable or cloud. Traces, spans, scores, and evals in one place.

ADD mapping — observability lives in the Harness:
  The Harness is the only layer with full visibility into what happened:
  - what context was sent to the Model
  - what the Model returned
  - which tools were called and with what inputs
  - how long each step took
  - where errors occurred

  The Model has no awareness of being traced. Tracing is a pure Harness concern.

What Langfuse gives you:
  - Traces: one per agent run
  - Spans: one per logical step (planning, tool call, generation)
  - Generations: LLM calls with input/output/tokens/cost
  - Scores: human or automated feedback attached to traces

Run:
    pip install -r requirements.txt
    cp .env.example .env
    # Start Langfuse: docker compose up  (see https://langfuse.com/docs/deployment/self-host)
    # Or use Langfuse Cloud: https://cloud.langfuse.com
    python agent.py
"""

import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv
from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe

load_dotenv()

# ── Infra: clients ────────────────────────────────────────────────────────────
anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Langfuse client — reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env
langfuse = Langfuse()

# ── Harness: tool definitions and execution ───────────────────────────────────
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


@observe(name="tool_execution")   # Harness span: one per tool call
def execute_tool(name: str, inputs: dict) -> str:
    langfuse_context.update_current_observation(
        input={"tool": name, "inputs": inputs},
        metadata={"tool_name": name},
    )
    if name == "get_weather":
        result = json.dumps({"city": inputs["city"], "temperature": "22°C", "condition": "sunny"})
    elif name == "calculate":
        try:
            result = str(eval(inputs["expression"], {"__builtins__": {}}))  # noqa: S307
        except Exception as e:
            result = f"Error: {e}"
    else:
        result = f"Unknown tool: {name}"
    langfuse_context.update_current_observation(output=result)
    return result


@observe(name="llm_call")         # Harness span: one per Model call
def call_model(messages: list, system: str) -> object:
    langfuse_context.update_current_observation(
        input={"messages": messages, "system": system},
        metadata={"model": "claude-sonnet-4-6"},
    )
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        tools=TOOLS,
        messages=messages,
    )
    # Record token usage for cost tracking
    langfuse_context.update_current_observation(
        output={"stop_reason": response.stop_reason},
        usage={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    return response


@observe(name="agent_run")        # Top-level trace: one per agent invocation
def run_agent(user_message: str) -> str:
    """ADD: @observe decorators are Harness instrumentation. Model is unaware."""
    langfuse_context.update_current_trace(
        name="agent_run",
        input=user_message,
        tags=["add-example", "single-agent"],
    )

    system = "You are a helpful assistant. Use tools when needed. Be concise."
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = call_model(messages, system)

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    langfuse_context.update_current_trace(output=block.text)
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

        return f"Unexpected stop reason: {response.stop_reason}"


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    queries = [
        "What's the weather in Tokyo?",
        "What is 1234 * 5678?",
    ]
    for q in queries:
        print(f"\n> {q}")
        answer = run_agent(q)
        print(answer)

        # Optionally add a score to the trace (e.g., from automated eval)
        # langfuse.score(trace_id=..., name="correctness", value=1.0)

    langfuse.flush()  # Ensure all events are sent before exit
    print("\nTraces available at your Langfuse dashboard.")
