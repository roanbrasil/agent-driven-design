"""
ReAct Loop — LangGraph Implementation
======================================
Same ReAct pattern as the manual example, now using LangGraph to model
the loop as an explicit state machine graph.

ADD mapping:
  - Model   : reasoning and tool call decisions at each node
  - Harness : graph definition, node functions, edge conditions,
              state schema, tool execution
  - Infra   : provider API, LangGraph runtime

LangGraph makes the Harness structure explicit: nodes are Harness functions,
edges are Harness routing decisions, and the graph is the loop.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import os
import json
from typing import Annotated, TypedDict
from dotenv import load_dotenv

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

load_dotenv()

# ── Harness: state schema ─────────────────────────────────────────────────────
# LangGraph state is a Harness concept — it defines what persists across nodes.
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ── Harness: tool definitions ─────────────────────────────────────────────────
@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return json.dumps({"city": city, "temperature": "18°C", "condition": "cloudy"})

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return str(eval(expression, {"__builtins__": {}}))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"

@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Search results for '{query}': [result 1] [result 2] [result 3]"

TOOLS = [get_weather, calculate, search_web]
TOOL_MAP = {t.name: t for t in TOOLS}

# ── Harness: model with tools bound ──────────────────────────────────────────
llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
).bind_tools(TOOLS)


# ── Harness: graph nodes ──────────────────────────────────────────────────────

def call_model(state: AgentState) -> AgentState:
    """ADD: invokes the Model. Everything else in this file is Harness."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def call_tools(state: AgentState) -> AgentState:
    """ADD: Harness executes tool calls requested by the Model."""
    last_message = state["messages"][-1]
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_fn = TOOL_MAP[tool_call["name"]]
        result = tool_fn.invoke(tool_call["args"])
        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )
    return {"messages": tool_messages}


# ── Harness: routing logic ────────────────────────────────────────────────────
def should_continue(state: AgentState) -> str:
    """ADD: Harness decides whether to call tools or end the loop."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


# ── Harness: graph construction ───────────────────────────────────────────────
# The graph makes the ReAct loop explicit as a state machine.
# agent → (tool_calls?) → tools → agent → ... → END
graph_builder = StateGraph(AgentState)
graph_builder.add_node("agent", call_model)
graph_builder.add_node("tools", call_tools)
graph_builder.set_entry_point("agent")
graph_builder.add_conditional_edges("agent", should_continue)
graph_builder.add_edge("tools", "agent")
graph = graph_builder.compile()


# ── Harness: run interface ────────────────────────────────────────────────────
def run_agent(user_message: str) -> str:
    result = graph.invoke({"messages": [HumanMessage(content=user_message)]})
    return result["messages"][-1].content


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    question = "What's the weather in London, and if the temperature were doubled, what would it be in Fahrenheit? Assume current temp is 18°C."
    print(f"Question: {question}\n")

    # Stream intermediate steps
    for event in graph.stream({"messages": [HumanMessage(content=question)]}):
        for node, state in event.items():
            print(f"\n── Node: {node} ──")
            for msg in state.get("messages", []):
                print(f"  {type(msg).__name__}: {msg.content[:200] if msg.content else '[tool call]'}")

    answer = run_agent(question)
    print(f"\n{'='*50}\nFinal Answer: {answer}")
