"""
Single Agent — LangChain (provider-agnostic)
=============================================
ADD mapping:
  - Model   : any ChatModel (Claude, OpenAI, etc.) — swappable via config
  - Harness : LangChain tool wrappers, AgentExecutor, prompt template
  - Infra   : provider API

LangChain sits entirely inside the Harness layer of ADD.
The Model is injected — you can swap providers without changing agent logic.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import os
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

load_dotenv()

# ── Harness: model selection (swappable) ─────────────────────────────────────
# Change PROVIDER in .env to switch between Claude and OpenAI without touching
# any other code. This is the ADD boundary in action.

PROVIDER = os.environ.get("PROVIDER", "anthropic")

if PROVIDER == "anthropic":
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(model="claude-sonnet-4-6", api_key=os.environ.get("ANTHROPIC_API_KEY"))
elif PROVIDER == "openai":
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o", api_key=os.environ.get("OPENAI_API_KEY"))
else:
    raise ValueError(f"Unknown provider: {PROVIDER}")


# ── Harness: tool definitions ─────────────────────────────────────────────────
@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    # Stub — replace with real API
    return f'{{"city": "{city}", "temperature": "22°C", "condition": "sunny"}}'


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression like '2 + 2' or '100 * 1.2'."""
    try:
        result = eval(expression, {"__builtins__": {}})  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Error: {e}"


TOOLS = [get_weather, calculate]

# ── Harness: prompt template ──────────────────────────────────────────────────
# System prompt and message structure are Harness responsibilities
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Use tools when needed. Be concise."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# ── Harness: agent construction ───────────────────────────────────────────────
# LangChain's AgentExecutor is a Harness component — it drives the loop,
# handles tool execution, and manages the scratchpad.
agent = create_tool_calling_agent(llm, TOOLS, prompt)
agent_executor = AgentExecutor(agent=agent, tools=TOOLS, verbose=True)


# ── Harness: run interface ────────────────────────────────────────────────────
def run_agent(user_message: str) -> str:
    result = agent_executor.invoke({"input": user_message})
    return result["output"]


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
