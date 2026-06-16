"""
Multi-Agent — Hierarchical (Orchestrator + Workers) with LangGraph
===================================================================
Topology: one Orchestrator agent delegates tasks to specialized Worker agents.

  Orchestrator — reasons about task decomposition and result assembly
  ├── ResearchWorker  — searches for information
  ├── AnalysisWorker  — performs analysis and calculations
  └── WriterWorker    — drafts written outputs

ADD mapping:
  - Model   : all four agents (each with its own system prompt = context boundary)
  - Harness : LangGraph graph, state schema, routing logic, worker dispatch,
              result collection, each worker's tool surface
  - Infra   : Anthropic API, LangGraph runtime

Key ADD concepts demonstrated:
  - Agent Context Boundaries: each worker has its own system prompt and tools
  - Agent Topology: hierarchical (orchestrator + workers)
  - Universal vs Conditional agents: Orchestrator is universal; workers are conditional

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import json
import os
import re
from typing import Annotated, Literal, TypedDict
from dotenv import load_dotenv

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

load_dotenv()

# ── Harness: model ────────────────────────────────────────────────────────────
llm = ChatAnthropic(model="claude-sonnet-4-6", api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── Harness: state schema ─────────────────────────────────────────────────────
class OrchestratorState(TypedDict):
    messages: Annotated[list, add_messages]
    task: str
    worker_results: dict          # collected results from workers
    next_worker: str | None       # Harness routing decision
    final_answer: str | None


# ── Harness: worker tool surfaces ─────────────────────────────────────────────
# Each worker has a different tool surface — this is the Agent Context Boundary.

@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Search results for '{query}': [result about {query}]"

@tool
def fetch_data(source: str, params: str = "") -> str:
    """Fetch structured data from a source."""
    return json.dumps({"source": source, "data": f"sample data for {params}"})

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return str(eval(expression, {"__builtins__": {}}))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"

@tool
def analyze_data(data: str, analysis_type: str) -> str:
    """Analyze data and return insights."""
    return f"Analysis ({analysis_type}) of '{data[:50]}...': key insight here"


# ── Harness: worker system prompts (Agent Context Boundaries) ─────────────────
WORKER_CONFIGS = {
    "research": {
        "system": "You are a research specialist. Your only job is to find information. Use search_web and fetch_data tools. Return a JSON with key: 'research_findings'.",
        "tools": [search_web, fetch_data],
    },
    "analysis": {
        "system": "You are an analysis specialist. Your only job is to analyze data and perform calculations. Use calculate and analyze_data tools. Return a JSON with key: 'analysis_results'.",
        "tools": [calculate, analyze_data],
    },
    "writer": {
        "system": "You are a writing specialist. Your only job is to draft clear, well-structured written content. No tools needed. Return a JSON with key: 'draft'.",
        "tools": [],
    },
}

ORCHESTRATOR_SYSTEM = """You are an orchestrator. Your job is to decompose tasks and delegate to specialists.

Available workers:
- research: finds information (use for: facts, data retrieval, lookups)
- analysis: analyzes and calculates (use for: math, comparisons, insights)
- writer: drafts text (use for: final written outputs)
- DONE: when all work is complete and you have a final answer

Respond with JSON:
{"next": "research|analysis|writer|DONE", "instruction": "what to do", "final_answer": "only when next=DONE"}
"""


# ── Harness: orchestrator node ────────────────────────────────────────────────
def orchestrator_node(state: OrchestratorState) -> OrchestratorState:
    """ADD: Orchestrator Model decides what to do next."""
    context = f"Task: {state['task']}\n\nWork done so far:\n"
    for worker, result in state.get("worker_results", {}).items():
        context += f"\n{worker}: {result}"

    response = llm.invoke([
        SystemMessage(content=ORCHESTRATOR_SYSTEM),
        HumanMessage(content=context + "\n\nWhat should be done next?"),
    ])

    raw = response.content.strip()
    # Harness parses structured output
    raw = re.sub(r"```json\n?", "", raw).replace("```", "").strip()
    decision = json.loads(raw)

    return {
        "messages": [response],
        "next_worker": decision["next"],
        "final_answer": decision.get("final_answer"),
    }


# ── Harness: worker node factory ──────────────────────────────────────────────
def make_worker_node(worker_name: str):
    """ADD: Each worker is a separate agent with its own context boundary."""
    config = WORKER_CONFIGS[worker_name]
    worker_llm = llm.bind_tools(config["tools"]) if config["tools"] else llm

    def worker_node(state: OrchestratorState) -> OrchestratorState:
        # Get the orchestrator's instruction for this worker
        last_orchestrator_msg = state["messages"][-1]
        raw = last_orchestrator_msg.content.strip()
        raw = re.sub(r"```json\n?", "", raw).replace("```", "").strip()
        instruction = json.loads(raw).get("instruction", state["task"])

        response = worker_llm.invoke([
            SystemMessage(content=config["system"]),
            HumanMessage(content=instruction),
        ])

        # Harness stores result in shared state
        results = dict(state.get("worker_results", {}))
        results[worker_name] = response.content

        print(f"\n[Worker: {worker_name}]\n{response.content[:300]}")
        return {"messages": [response], "worker_results": results}

    return worker_node


# ── Harness: routing ──────────────────────────────────────────────────────────
def route(state: OrchestratorState) -> str:
    """ADD: Harness routes based on orchestrator decision."""
    return state.get("next_worker", END)


# ── Harness: graph construction ───────────────────────────────────────────────
graph_builder = StateGraph(OrchestratorState)
graph_builder.add_node("orchestrator", orchestrator_node)
graph_builder.add_node("research", make_worker_node("research"))
graph_builder.add_node("analysis", make_worker_node("analysis"))
graph_builder.add_node("writer", make_worker_node("writer"))

graph_builder.set_entry_point("orchestrator")
graph_builder.add_conditional_edges(
    "orchestrator",
    route,
    {"research": "research", "analysis": "analysis", "writer": "writer", "DONE": END},
)
graph_builder.add_edge("research", "orchestrator")
graph_builder.add_edge("analysis", "orchestrator")
graph_builder.add_edge("writer", "orchestrator")

graph = graph_builder.compile()


# ── Harness: run interface ────────────────────────────────────────────────────
def run_multi_agent(task: str) -> str:
    result = graph.invoke({
        "task": task,
        "messages": [],
        "worker_results": {},
        "next_worker": None,
        "final_answer": None,
    })
    return result.get("final_answer", "No final answer produced.")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    task = "Research the benefits of ReAct loops in LLM systems, analyze the key tradeoffs, and write a three-sentence summary."
    print(f"Task: {task}\n{'='*60}")
    answer = run_multi_agent(task)
    print(f"\n{'='*60}\nFinal Answer:\n{answer}")
