"""
Human-in-the-Loop Agent — Manual Implementation (Anthropic)  [ADVANCED]
========================================================================
The Human-in-the-Loop (HITL) pattern inserts a human approval checkpoint
before executing high-risk or irreversible tool calls.

The Model proposes an action; the Harness intercepts it and asks a human
to approve, reject, or modify it before execution proceeds.

ADD mapping:
  - Model   : reasons about what actions are needed, produces tool calls
  - Harness : risk classifier, approval gate, execution (only after approval),
              loop control, action modification
  - Infra   : Anthropic API, stdin (human approval channel)

Demonstrated risk tiers:
  - LOW    → auto-execute (read operations, lookups)
  - MEDIUM → ask for confirmation
  - HIGH   → require explicit typed approval + show impact

Key ADD insight: Human approval is a Harness capability.
The Model has no knowledge that approval happened — it only sees the tool result.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import json
import os
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"

# ── Harness: tool definitions ─────────────────────────────────────────────────
TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Safe, read-only operation.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path to read"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. This will overwrite existing content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "delete_file",
        "description": "Permanently delete a file. This action is irreversible.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email to a recipient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
]

# ── Harness: risk classification ──────────────────────────────────────────────
# The Harness — not the Model — owns this policy.
RISK_LEVELS: dict[str, str] = {
    "read_file": "low",
    "list_directory": "low",
    "write_file": "medium",
    "send_email": "medium",
    "delete_file": "high",
}

RISK_DESCRIPTIONS: dict[str, str] = {
    "low": "Safe read-only operation — executing automatically.",
    "medium": "This action modifies external state. Approval required.",
    "high": "IRREVERSIBLE action with significant impact. Explicit confirmation required.",
}


# ── Harness: approval gate ────────────────────────────────────────────────────
def request_approval(tool_name: str, tool_input: dict) -> tuple[bool, dict]:
    """
    ADD: This is the HITL gate. The Model never sees this function —
    it only sees the tool result after the gate resolves.
    Returns (approved, possibly_modified_input).
    """
    risk = RISK_LEVELS.get(tool_name, "medium")
    print(f"\n{'━'*60}")
    print(f"  ACTION REQUIRED: [{risk.upper()}] {tool_name}")
    print(f"  {RISK_DESCRIPTIONS[risk]}")
    print(f"  Input: {json.dumps(tool_input, indent=2)}")
    print(f"{'━'*60}")

    if risk == "low":
        print("  → Auto-approved (low risk)")
        return True, tool_input

    if risk == "medium":
        answer = input("  Approve? [y/n]: ").strip().lower()
        return answer == "y", tool_input

    if risk == "high":
        print(f"  Type the tool name '{tool_name}' to confirm, or press Enter to cancel:")
        answer = input("  > ").strip()
        return answer == tool_name, tool_input

    return False, tool_input


# ── Harness: tool execution stubs ────────────────────────────────────────────
def execute_tool(name: str, inputs: dict) -> str:
    """Stub implementations — replace with real I/O in production."""
    if name == "read_file":
        return f"[Contents of {inputs['path']}]\nLine 1: Hello world\nLine 2: Sample data"
    if name == "list_directory":
        return f"[Files in {inputs['path']}]\n- report.csv\n- config.json\n- archive/"
    if name == "write_file":
        return f"Written {len(inputs['content'])} chars to {inputs['path']}"
    if name == "delete_file":
        return f"Deleted {inputs['path']}"
    if name == "send_email":
        return f"Email sent to {inputs['to']} — subject: {inputs['subject']}"
    return f"Unknown tool: {name}"


# ── Harness: HITL agentic loop ────────────────────────────────────────────────
def run_hitl_agent(user_message: str) -> str:
    """
    ADD: Standard agentic loop with the HITL gate inserted before every tool execution.
    The Model proposes; the Harness decides whether to execute.
    """
    messages = [{"role": "user", "content": user_message}]
    system = (
        "You are a file management assistant. "
        "Use tools to help the user manage files and send communications. "
        "Always explain what you are about to do before calling a tool."
    )

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOLS,
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
                if hasattr(block, "text") and block.text:
                    print(f"\nAgent: {block.text}")
                if block.type == "tool_use":
                    # ADD: Harness intercepts EVERY tool call and gates it
                    approved, final_input = request_approval(block.name, block.input)

                    if approved:
                        result = execute_tool(block.name, final_input)
                        print(f"  ✓ Executed: {result}")
                    else:
                        result = f"Action '{block.name}' was rejected by the user."
                        print(f"  ✗ Rejected.")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        return f"Unexpected stop reason: {response.stop_reason}"


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    task = (
        "Please: (1) list the files in /data, "
        "(2) read the file /data/report.csv, "
        "(3) write a summary to /data/summary.txt, "
        "(4) delete /data/old_backup.csv, "
        "(5) email the summary to manager@example.com"
    )
    print(f"Task: {task}\n")
    result = run_hitl_agent(task)
    print(f"\n{'='*60}\nFinal: {result}")
