"""
Reflection Loop — Manual Implementation (Anthropic)
====================================================
The Reflection pattern uses two Model calls per iteration:
  1. Generator: produces a draft output
  2. Critic: evaluates the draft and suggests improvements

The loop continues until the Critic approves or max iterations are reached.

ADD mapping:
  - Model   : both Generator and Critic roles (can be the same or different models)
  - Harness : loop driver, draft/critique routing, stopping condition,
              prompt construction for each role, convergence detection
  - Infra   : Anthropic API

Key ADD insight: the Generator and Critic are two separate Model invocations
with different system prompts (Harness decisions). They share the same
underlying Model capability but operate in different contexts.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import os
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── Harness: role-specific system prompts ─────────────────────────────────────
GENERATOR_SYSTEM = """You are an expert writer. 
Given a task, produce a high-quality draft response.
Be thorough and precise."""

CRITIC_SYSTEM = """You are a rigorous critic and editor.
Given a draft response, evaluate it and provide specific, actionable feedback.

If the draft is satisfactory, respond with exactly: APPROVED
If it needs improvement, respond with: NEEDS_REVISION
Followed by a numbered list of specific improvements needed.

Be demanding but fair. Approve only when the response is genuinely good."""

REVISER_SYSTEM = """You are an expert writer doing a revision.
You will receive an original draft and critic feedback.
Produce an improved version that addresses all the feedback points.
Do not mention the revision process — just produce the improved content."""


# ── Harness: individual Model calls ──────────────────────────────────────────
def generate(task: str) -> str:
    """ADD: Generator Model call. Harness provides the task context."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=GENERATOR_SYSTEM,
        messages=[{"role": "user", "content": task}],
    )
    return response.content[0].text


def critique(task: str, draft: str) -> str:
    """ADD: Critic Model call. Harness constructs the critique context."""
    prompt = f"""Original task: {task}

Draft to evaluate:
{draft}

Evaluate this draft."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=CRITIC_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def revise(task: str, draft: str, feedback: str) -> str:
    """ADD: Reviser Model call. Harness provides draft + feedback context."""
    prompt = f"""Original task: {task}

Current draft:
{draft}

Critic feedback:
{feedback}

Produce an improved version."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=REVISER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── Harness: reflection loop ──────────────────────────────────────────────────
def run_reflection_agent(task: str, max_iterations: int = 3) -> dict:
    """
    ADD: The loop, stopping condition, and iteration tracking are all Harness.
    The Model only sees individual generation/critique/revision prompts.
    """
    print(f"Task: {task}\n")
    print("─" * 60)

    # Step 1: Generate initial draft
    draft = generate(task)
    print(f"[Iteration 0 — Initial Draft]\n{draft}\n")

    history = [{"iteration": 0, "draft": draft, "feedback": None}]

    for i in range(1, max_iterations + 1):
        print(f"[Iteration {i} — Critique]")

        # Step 2: Critique the draft
        feedback = critique(task, draft)
        print(f"{feedback}\n")

        # ADD: Harness checks stopping condition
        if feedback.strip().startswith("APPROVED"):
            print(f"✓ Draft approved at iteration {i}")
            return {"final": draft, "iterations": i, "history": history}

        # Step 3: Revise based on feedback
        print(f"[Iteration {i} — Revision]")
        draft = revise(task, draft, feedback)
        print(f"{draft}\n")
        print("─" * 60)

        history.append({"iteration": i, "draft": draft, "feedback": feedback})

    print(f"Max iterations ({max_iterations}) reached.")
    return {"final": draft, "iterations": max_iterations, "history": history}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    task = "Write a concise explanation of why Agent Context Boundaries matter in multi-agent LLM systems. Target audience: senior software engineers."
    result = run_reflection_agent(task, max_iterations=3)
    print(f"\n{'='*60}")
    print(f"Final output (after {result['iterations']} iteration(s)):\n")
    print(result["final"])
