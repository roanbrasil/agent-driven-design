"""
Plan-Execute Loop — Manual Implementation (Anthropic)
=====================================================
The Plan-Execute pattern separates planning from execution:
  1. Planner: receives the goal and produces a structured list of steps
  2. Executor: executes each step in sequence, using tools as needed
  3. Synthesizer: takes all step results and produces the final answer

ADD mapping:
  - Model   : Planner (reasoning about what steps are needed),
              Executor (reasoning about how to execute each step),
              Synthesizer (reasoning about how to combine results)
  - Harness : plan parsing, step dispatch, result collection,
              executor loop, synthesis trigger
  - Infra   : Anthropic API

Key ADD insight: three different Model invocations with different system prompts
(Harness decisions) — same underlying Model, three different contexts and roles.

Reference: Wang et al. (2023) — Plan-and-Solve Prompting

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

# ── Harness: role system prompts ──────────────────────────────────────────────
PLANNER_SYSTEM = """You are a planning agent. Given a goal, break it down into clear, 
sequential steps that can each be executed independently.

Respond ONLY with a JSON array of steps. Each step has:
- "id": integer starting at 1
- "description": what to do
- "tool": the tool to use ("get_weather", "calculate", "search_web", or null)
- "tool_input": the input for the tool (or null)

Example:
[
  {"id": 1, "description": "Get weather in Paris", "tool": "get_weather", "tool_input": {"city": "Paris"}},
  {"id": 2, "description": "Calculate something", "tool": "calculate", "tool_input": {"expression": "18 * 2"}}
]

Output ONLY the JSON array, nothing else."""

EXECUTOR_SYSTEM = """You are an execution agent. You will be given a step to execute
and the results of any tools that were called. Summarize the result of this step clearly
in one or two sentences."""

SYNTHESIZER_SYSTEM = """You are a synthesis agent. You will receive a goal and the results
of all execution steps. Produce a clear, complete final answer that addresses the original goal."""


# ── Harness: tool registry ────────────────────────────────────────────────────
def get_weather(city: str) -> str:
    return json.dumps({"city": city, "temperature": "18°C", "condition": "partly cloudy"})

def calculate(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"

def search_web(query: str) -> str:
    return f"Search results for '{query}': [sample result 1] [sample result 2]"

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "calculate": calculate,
    "search_web": search_web,
}


# ── Harness: planner call ─────────────────────────────────────────────────────
def plan(goal: str) -> list[dict]:
    """ADD: Model decides what steps are needed. Harness parses the result."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=PLANNER_SYSTEM,
        messages=[{"role": "user", "content": f"Goal: {goal}"}],
    )
    raw = response.content[0].text.strip()
    # Harness parses structured output
    raw = re.sub(r"```json\n?", "", raw).replace("```", "").strip()
    return json.loads(raw)


# ── Harness: executor call ────────────────────────────────────────────────────
def execute_step(step: dict) -> str:
    """ADD: Harness runs the tool; Model summarizes the result."""
    tool_result = None
    if step.get("tool") and step["tool"] in TOOL_REGISTRY:
        tool_input = step.get("tool_input") or {}
        tool_result = TOOL_REGISTRY[step["tool"]](**tool_input)

    prompt = f"Step: {step['description']}"
    if tool_result:
        prompt += f"\nTool result: {tool_result}"
    prompt += "\nSummarize the result of this step."

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=EXECUTOR_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── Harness: synthesizer call ─────────────────────────────────────────────────
def synthesize(goal: str, step_results: list[dict]) -> str:
    """ADD: Model produces final answer given all step results."""
    results_text = "\n".join(
        f"Step {r['id']}: {r['description']}\nResult: {r['result']}"
        for r in step_results
    )
    prompt = f"Goal: {goal}\n\nStep results:\n{results_text}\n\nProvide the final answer."
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYNTHESIZER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── Harness: plan-execute orchestration ───────────────────────────────────────
def run_plan_execute_agent(goal: str) -> str:
    """ADD: Orchestration is entirely Harness. Model sees isolated prompts."""
    print(f"Goal: {goal}\n{'─'*60}")

    # Phase 1: Plan
    print("[Phase 1: Planning]")
    steps = plan(goal)
    for step in steps:
        print(f"  Step {step['id']}: {step['description']}")
    print()

    # Phase 2: Execute each step
    print("[Phase 2: Execution]")
    step_results = []
    for step in steps:
        print(f"  Executing step {step['id']}...")
        result = execute_step(step)
        step_results.append({**step, "result": result})
        print(f"  → {result}\n")

    # Phase 3: Synthesize
    print("[Phase 3: Synthesis]")
    final_answer = synthesize(goal, step_results)
    return final_answer


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    goal = "What is the weather in London and Tokyo? Convert both temperatures to Fahrenheit and tell me which city is warmer."
    result = run_plan_execute_agent(goal)
    print(f"\n{'='*60}\nFinal Answer:\n{result}")
