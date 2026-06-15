"""
ReAct Loop — Manual Implementation (Anthropic)
===============================================
ReAct = Reason + Act. The Model alternates between reasoning about what to do
and acting (calling tools). The loop continues until the Model reasons that
it has enough information to produce a final answer.

ADD mapping:
  - Model   : reasoning steps (Thought) and action decisions (Act)
  - Harness : loop driver, tool execution, scratchpad construction,
              stopping condition, output extraction
  - Infra   : Anthropic API

The ReAct pattern makes the Model's internal reasoning visible by asking it
to produce explicit Thought / Action / Observation sequences.

Reference: Yao et al. (2022) — ReAct: Synergizing Reasoning and Acting in LLMs

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import json
import os
import re
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── Harness: system prompt defines the ReAct format ──────────────────────────
# The format itself is a Harness decision — the Model follows it.
SYSTEM_PROMPT = """You are a helpful assistant that solves problems step by step.

Use the following format strictly:

Thought: reason about what you need to do next
Action: tool_name
Action Input: {"param": "value"}
Observation: (the result of the action — provided by the system)
... (repeat Thought/Action/Observation as needed)
Thought: I now have enough information to answer
Final Answer: your complete answer to the user

Available tools:
- get_weather: Get current weather. Input: {"city": "string"}
- calculate: Evaluate math. Input: {"expression": "string"}
- search_web: Search for information. Input: {"query": "string"}

Begin!
"""

# ── Harness: tool registry ────────────────────────────────────────────────────
def get_weather(city: str) -> str:
    # Stub
    return json.dumps({"city": city, "temperature": "18°C", "condition": "cloudy"})

def calculate(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"

def search_web(query: str) -> str:
    # Stub
    return f"Search results for '{query}': [result 1] [result 2] [result 3]"

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "calculate": calculate,
    "search_web": search_web,
}

# ── Harness: output parsers ───────────────────────────────────────────────────
def parse_action(text: str) -> tuple[str, dict] | None:
    action_match = re.search(r"Action:\s*(\w+)", text)
    input_match = re.search(r"Action Input:\s*(\{.*?\})", text, re.DOTALL)
    if action_match and input_match:
        tool_name = action_match.group(1).strip()
        tool_input = json.loads(input_match.group(1))
        return tool_name, tool_input
    return None

def parse_final_answer(text: str) -> str | None:
    match = re.search(r"Final Answer:\s*(.+)", text, re.DOTALL)
    return match.group(1).strip() if match else None

# ── Harness: ReAct loop ───────────────────────────────────────────────────────
def run_react_agent(user_message: str, max_steps: int = 10) -> str:
    """
    ADD: This loop is entirely a Harness responsibility.
    The Model produces Thought/Action text; the Harness parses it,
    executes tools, appends Observations, and decides when to stop.
    """
    scratchpad = f"Question: {user_message}\n"
    messages = [{"role": "user", "content": scratchpad}]

    for step in range(max_steps):
        print(f"\n── Step {step + 1} ──────────────────────")

        # ADD: Model reasons given the scratchpad constructed by the Harness
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
            stop_sequences=["Observation:"],  # Harness controls when Model stops
        )

        assistant_text = response.content[0].text
        print(assistant_text)

        # ADD: Harness checks for final answer first
        final = parse_final_answer(assistant_text)
        if final:
            return final

        # ADD: Harness parses the action and executes it
        parsed = parse_action(assistant_text)
        if not parsed:
            # Model didn't follow the format — Harness handles gracefully
            return assistant_text

        tool_name, tool_input = parsed
        if tool_name not in TOOL_REGISTRY:
            observation = f"Error: tool '{tool_name}' not found."
        else:
            observation = TOOL_REGISTRY[tool_name](**tool_input)

        print(f"Observation: {observation}")

        # ADD: Harness appends observation to scratchpad and continues loop
        messages.append({"role": "assistant", "content": assistant_text})
        messages.append({"role": "user", "content": f"Observation: {observation}\n"})

    return "Max steps reached without a final answer."


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    question = "What's the weather in London, and if the temperature were doubled, what would it be in Fahrenheit? Assume current temp is 18°C."
    print(f"Question: {question}\n")
    answer = run_react_agent(question)
    print(f"\n{'='*50}\nFinal Answer: {answer}")
