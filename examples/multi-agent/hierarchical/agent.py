"""
Multi-Agent — Hierarchical (Orchestrator + Workers) with Anthropic SDK
======================================================================
Topology: one Orchestrator agent delegates tasks to specialized Worker agents.

  Orchestrator — reasons about task decomposition and result assembly
  ├── ResearchWorker  — finds information
  ├── AnalysisWorker  — performs analysis and calculations
  └── WriterWorker    — drafts written outputs

ADD mapping:
  - Model   : all agents share claude-sonnet-4-6; each has its own system prompt
              (= its own Agent Context Boundary)
  - Harness : orchestrator loop, worker dispatch, result collection, routing,
              each worker's tool surface, handoff schemas
  - Infra   : Anthropic API

Key ADD concepts demonstrated:
  - Agent Context Boundaries: each worker's system prompt is its boundary
  - Agent Topology: hierarchical (orchestrator + workers)
  - Universal vs Conditional agents: Orchestrator is universal; workers are conditional
  - Handoff: orchestrator output → structured instruction → worker input

No framework. Pure Anthropic SDK.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import json
import os
import re
from anthropic import Anthropic

# ── Infra ─────────────────────────────────────────────────────────────────────
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


# ── Harness: worker tool definitions and execution ────────────────────────────
# Each worker has its own tool surface — this IS the Agent Context Boundary.

RESEARCH_TOOLS = [
    {
        "name": "search_web",
        "description": "Search the web for information on a topic.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
    {
        "name": "fetch_article",
        "description": "Retrieve the content of an article by title or URL.",
        "input_schema": {
            "type": "object",
            "properties": {"source": {"type": "string", "description": "Article title or URL"}},
            "required": ["source"],
        },
    },
]

ANALYSIS_TOOLS = [
    {
        "name": "calculate",
        "description": "Evaluate a mathematical expression.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "Math expression"}},
            "required": ["expression"],
        },
    },
    {
        "name": "compare",
        "description": "Compare two items along a specified dimension.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_a": {"type": "string"},
                "item_b": {"type": "string"},
                "dimension": {"type": "string", "description": "What to compare (e.g. cost, speed, accuracy)"},
            },
            "required": ["item_a", "item_b", "dimension"],
        },
    },
]


def execute_research_tool(name: str, inputs: dict) -> str:
    if name == "search_web":
        return f"Search results for '{inputs['query']}': [article 1], [article 2], [article 3]"
    if name == "fetch_article":
        return f"Content of '{inputs['source']}': [detailed content about the topic]"
    return f"Unknown tool: {name}"


def execute_analysis_tool(name: str, inputs: dict) -> str:
    if name == "calculate":
        try:
            result = eval(inputs["expression"], {"__builtins__": {}})  # noqa: S307
            return str(result)
        except Exception as e:
            return f"Error: {e}"
    if name == "compare":
        return (
            f"Comparison of {inputs['item_a']} vs {inputs['item_b']} "
            f"on {inputs['dimension']}: [analysis result]"
        )
    return f"Unknown tool: {name}"


# ── Harness: worker agent ─────────────────────────────────────────────────────
def run_worker(system: str, tools: list, execute_fn, instruction: str) -> str:
    """
    ADD: A worker agent is Model + Harness within a narrow context boundary.
    The system prompt defines the boundary; tools define the capability surface.
    """
    messages = [{"role": "user", "content": instruction}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=tools if tools else [],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_fn(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        return f"Unexpected stop reason: {response.stop_reason}"


# ── Harness: worker configurations ───────────────────────────────────────────
WORKERS = {
    "research": {
        "system": (
            "You are a research specialist. Your only job is to find accurate information. "
            "Use the available tools to search and retrieve content. "
            "Return your findings as plain text, clearly organized."
        ),
        "tools": RESEARCH_TOOLS,
        "execute": execute_research_tool,
    },
    "analysis": {
        "system": (
            "You are an analysis specialist. Your only job is to analyze information and perform calculations. "
            "Use the available tools for math and comparisons. "
            "Return your analysis as plain text with clear conclusions."
        ),
        "tools": ANALYSIS_TOOLS,
        "execute": execute_analysis_tool,
    },
    "writer": {
        "system": (
            "You are a writing specialist. Your only job is to produce clear, well-structured text. "
            "You receive research and analysis as context. Write the final output. "
            "No tools available — use only what is provided."
        ),
        "tools": [],
        "execute": lambda name, inputs: "",
    },
}


# ── Harness: orchestrator ─────────────────────────────────────────────────────
ORCHESTRATOR_SYSTEM = """You are a task orchestrator. You decompose tasks and delegate to specialists.

Available workers:
- research: finds and retrieves information
- analysis: performs analysis and calculations
- writer: produces final written output

Respond with a JSON object:
{
  "next": "research" | "analysis" | "writer" | "DONE",
  "instruction": "specific instruction for the next worker",
  "final_answer": "only include this field when next is DONE"
}

Rules:
- Always assign work to one worker at a time
- When all work is complete, set next to DONE and provide final_answer
- The instruction must be self-contained — the worker does not have prior context
"""


def orchestrate(task: str, max_steps: int = 10) -> str:
    """
    ADD: The orchestrator loop is a Harness responsibility.
    The orchestrator Model reasons about what to do next;
    the Harness executes the decision by dispatching to the right worker.
    """
    results: dict[str, str] = {}

    for step in range(max_steps):
        # Build context for the orchestrator
        context = f"Task: {task}\n"
        if results:
            context += "\nWork completed so far:\n"
            for worker, result in results.items():
                context += f"\n[{worker}]:\n{result}\n"
        context += "\nWhat should happen next?"

        # ADD: Orchestrator Model decides what to delegate
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=ORCHESTRATOR_SYSTEM,
            messages=[{"role": "user", "content": context}],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r"```json\n?", "", raw).replace("```", "").strip()
        decision = json.loads(raw)

        next_worker = decision.get("next")
        print(f"\n── Step {step + 1}: Orchestrator → {next_worker}")

        if next_worker == "DONE":
            return decision.get("final_answer", "No final answer.")

        if next_worker not in WORKERS:
            return f"Orchestrator referenced unknown worker: {next_worker}"

        # ADD: Harness dispatches to the chosen worker
        instruction = decision.get("instruction", task)
        print(f"   Instruction: {instruction}")

        cfg = WORKERS[next_worker]
        result = run_worker(cfg["system"], cfg["tools"], cfg["execute"], instruction)
        results[next_worker] = result
        print(f"   Result preview: {result[:120]}...")

    return "Max orchestration steps reached."


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    task = (
        "Research what ReAct loops are in LLM systems, "
        "analyze the key trade-offs versus single-call approaches, "
        "and write a three-sentence summary."
    )
    print(f"Task: {task}\n{'=' * 60}")
    answer = orchestrate(task)
    print(f"\n{'=' * 60}\nFinal Answer:\n{answer}")
