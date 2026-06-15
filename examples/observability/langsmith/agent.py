"""
Observability — LangSmith
==========================
LangSmith is LangChain's observability platform.
Tightly integrated with LangChain/LangGraph; also works standalone.

Key differences from Langfuse:
  - Native LangChain/LangGraph tracing (zero config when using LC)
  - Dataset management and automated evals built-in
  - Annotation queues for human review
  - Requires LangChain SDK for the cleanest integration

ADD mapping — same principle as Langfuse:
  Tracing is a Harness concern. The Model is unaware.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import json
import os
from dotenv import load_dotenv

# LangSmith tracing activates automatically when these env vars are set
load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = os.environ.get("LANGCHAIN_PROJECT", "add-examples")

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client
from langsmith.run_helpers import traceable

# ── Infra: clients ────────────────────────────────────────────────────────────
langsmith_client = Client()
llm = ChatAnthropic(model="claude-sonnet-4-6", api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── Harness: tools ────────────────────────────────────────────────────────────
@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return json.dumps({"city": city, "temperature": "22°C", "condition": "sunny"})

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return str(eval(expression, {"__builtins__": {}}))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"

TOOLS = [get_weather, calculate]


# ── Harness: agent construction ───────────────────────────────────────────────
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Use tools when needed. Be concise."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, TOOLS, prompt)
# LangChain automatically traces AgentExecutor when LANGCHAIN_TRACING_V2=true
agent_executor = AgentExecutor(agent=agent, tools=TOOLS, verbose=True)


# ── Harness: traceable wrapper ────────────────────────────────────────────────
@traceable(name="agent_run", tags=["add-example"])
def run_agent(user_message: str) -> str:
    """
    ADD: @traceable is Harness instrumentation.
    LangChain auto-traces internal steps; @traceable adds the outer span.
    """
    result = agent_executor.invoke({"input": user_message})
    return result["output"]


# ── Harness: create evaluation dataset (optional) ────────────────────────────
def create_eval_dataset():
    """
    ADD: Evals live in the Harness layer. They test the Model within its
    context, not the Model in isolation. The dataset is a Harness artifact.
    """
    dataset_name = "add-weather-calc-eval"
    if not any(d.name == dataset_name for d in langsmith_client.list_datasets()):
        dataset = langsmith_client.create_dataset(
            dataset_name,
            description="Eval dataset for single-agent weather/calc examples",
        )
        examples = [
            {
                "inputs": {"question": "What's the weather in Tokyo?"},
                "outputs": {"answer": "Tokyo"},  # expected to mention Tokyo
            },
            {
                "inputs": {"question": "What is 100 * 1.2?"},
                "outputs": {"answer": "120"},
            },
        ]
        for ex in examples:
            langsmith_client.create_example(
                inputs=ex["inputs"],
                outputs=ex["outputs"],
                dataset_id=dataset.id,
            )
        print(f"Dataset '{dataset_name}' created with {len(examples)} examples.")
    return dataset_name


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    queries = [
        "What's the weather in Tokyo?",
        "What is 1234 * 5678?",
    ]
    for q in queries:
        print(f"\n> {q}")
        print(run_agent(q))

    print("\nTraces available at https://smith.langchain.com")

    # Optionally create an eval dataset
    # dataset_name = create_eval_dataset()
    # print(f"Eval dataset ready: {dataset_name}")
