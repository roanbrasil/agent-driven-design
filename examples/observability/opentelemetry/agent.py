"""
Observability — OpenTelemetry (provider-agnostic)
==================================================
OpenTelemetry (OTel) is the CNCF standard for distributed tracing.
Using OTel directly means your traces are backend-agnostic:
  - Send to Langfuse (OTLP endpoint)
  - Send to Phoenix (OTLP endpoint)
  - Send to Jaeger, Zipkin, Grafana Tempo, Honeycomb, Datadog...
  - Send to stdout for local debugging

This example uses the OTLP HTTP exporter. Change the endpoint to
switch backends without changing any instrumentation code.

ADD mapping: same principle — tracing is Harness, Model is unaware.
OTel gives you maximum portability at the cost of more manual setup.

Run:
    pip install -r requirements.txt
    cp .env.example .env

    # Option A — stdout (no backend needed):
    OTEL_BACKEND=stdout python agent.py

    # Option B — Jaeger (docker):
    docker run -d -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one
    OTEL_BACKEND=jaeger python agent.py
    # Open http://localhost:16686

    # Option C — Langfuse OTLP:
    OTEL_BACKEND=langfuse python agent.py
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()

# ── Infra: OTel setup ─────────────────────────────────────────────────────────
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

BACKEND = os.environ.get("OTEL_BACKEND", "stdout")

resource = Resource.create({"service.name": "add-agent", "service.version": "0.1.0"})
provider = TracerProvider(resource=resource)

if BACKEND == "stdout":
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
elif BACKEND == "jaeger":
    exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
elif BACKEND == "langfuse":
    import base64
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "")
    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    exporter = OTLPSpanExporter(
        endpoint=f"{host}/api/public/otel/v1/traces",
        headers={"Authorization": f"Basic {auth}"},
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
else:
    raise ValueError(f"Unknown OTEL_BACKEND: {BACKEND}")

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("add.agent")

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
    with tracer.start_as_current_span(f"tool.{name}") as span:
        # OTel semantic conventions for LLM tooling
        span.set_attribute("tool.name", name)
        span.set_attribute("tool.input", json.dumps(inputs))
        if name == "get_weather":
            result = json.dumps({"city": inputs["city"], "temperature": "22°C", "condition": "sunny"})
        elif name == "calculate":
            try:
                result = str(eval(inputs["expression"], {"__builtins__": {}}))  # noqa: S307
            except Exception as e:
                result = f"Error: {e}"
        else:
            result = f"Unknown: {name}"
        span.set_attribute("tool.output", result)
        return result


# ── Harness: agentic loop ─────────────────────────────────────────────────────
def run_agent(user_message: str) -> str:
    with tracer.start_as_current_span("agent.run") as root:
        root.set_attribute("input.value", user_message)
        root.set_attribute("gen_ai.system", "anthropic")

        system = "You are a helpful assistant. Use tools when needed. Be concise."
        messages = [{"role": "user", "content": user_message}]

        while True:
            with tracer.start_as_current_span("gen_ai.completion") as llm_span:
                # OpenTelemetry GenAI semantic conventions
                llm_span.set_attribute("gen_ai.request.model", "claude-sonnet-4-6")
                llm_span.set_attribute("gen_ai.request.max_tokens", 1024)

                response = anthropic_client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=system,
                    tools=TOOLS,
                    messages=messages,
                )

                llm_span.set_attribute("gen_ai.response.finish_reasons", [response.stop_reason])
                llm_span.set_attribute("gen_ai.usage.input_tokens", response.usage.input_tokens)
                llm_span.set_attribute("gen_ai.usage.output_tokens", response.usage.output_tokens)

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        root.set_attribute("output.value", block.text)
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

            return f"Unexpected: {response.stop_reason}"


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Tracing backend: {BACKEND}\n")
    queries = ["What's the weather in Tokyo?", "What is 1234 * 5678?"]
    for q in queries:
        print(f"> {q}")
        print(run_agent(q), "\n")

    # Flush spans before exit
    provider.force_flush()
