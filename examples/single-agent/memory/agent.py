"""
Single Agent with Memory — Anthropic  [INTERMEDIATE]
=====================================================
Demonstrates how the Harness maintains state across turns.
The Model is stateless — memory is entirely a Harness responsibility.

Two kinds of memory:
  - Short-term: full message history (conversation window)
  - Long-term:  extracted facts stored in a dict and injected into future prompts

ADD mapping:
  - Model   : conversation, answer questions, extract facts on demand
  - Harness : memory store, fact injection, extraction trigger,
              conversation history management, turn loop
  - Infra   : Anthropic API

Run:
    pip install -r requirements.txt
    cp .env.example .env   # add ANTHROPIC_API_KEY
    python agent.py
"""

import os
import json
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"

# ── Harness: memory store ─────────────────────────────────────────────────────
# This dict is the Harness-managed long-term memory.
# The Model never writes here directly — the Harness extracts facts and stores them.
memory: dict[str, str] = {}

# Short-term memory: full conversation history
conversation: list[dict] = []


# ── Harness: fact extraction ──────────────────────────────────────────────────
EXTRACTOR_SYSTEM = """You are a fact extractor. Given a conversation turn, extract any
personal facts about the user (name, job, preferences, location, goals, etc.).

Respond ONLY with a JSON object where keys are fact names and values are the facts.
If no new facts, respond with {}.

Examples:
  Input: "I'm Maria and I work as a nurse in São Paulo"
  Output: {"name": "Maria", "job": "nurse", "city": "São Paulo"}

  Input: "What's the weather today?"
  Output: {}
"""


def extract_facts(user_message: str) -> dict:
    """ADD: Harness triggers a separate Model call to extract facts after each turn."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=EXTRACTOR_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )
    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ── Harness: memory injection ─────────────────────────────────────────────────
def build_system_prompt() -> str:
    """ADD: Harness injects stored facts into every Model call."""
    base = (
        "You are a helpful personal assistant with memory. "
        "Be concise and conversational."
    )
    if not memory:
        return base
    facts = "\n".join(f"  - {k}: {v}" for k, v in memory.items())
    return f"{base}\n\nWhat you know about this user:\n{facts}"


# ── Harness: single conversation turn ────────────────────────────────────────
def chat(user_message: str) -> str:
    """
    ADD: Each turn the Harness:
      1. Appends the user message to short-term history
      2. Calls the Model with injected long-term memory
      3. Stores the assistant reply in history
      4. Extracts new facts and updates the memory store
    """
    conversation.append({"role": "user", "content": user_message})

    # ADD: Model answers using the injected memory context
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=build_system_prompt(),
        messages=conversation,
    )
    reply = response.content[0].text
    conversation.append({"role": "assistant", "content": reply})

    # ADD: Harness extracts facts and updates long-term memory
    new_facts = extract_facts(user_message)
    if new_facts:
        memory.update(new_facts)
        print(f"  [memory updated: {new_facts}]")

    return reply


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Agent with Memory — type 'quit' to exit, 'memory' to inspect store\n")
    turns = [
        "Hi! My name is Ana and I'm a software engineer in Recife.",
        "I'm learning about LLM agents for a project at work.",
        "What do you know about me so far?",
        "Can you suggest a good starting point for my project given my background?",
    ]
    for msg in turns:
        print(f"User: {msg}")
        reply = chat(msg)
        print(f"Agent: {reply}\n")

    print(f"\n── Final memory store ──\n{json.dumps(memory, indent=2, ensure_ascii=False)}")
