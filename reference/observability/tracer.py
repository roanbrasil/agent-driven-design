"""
Trace capture for the ADD reference system.

In production you would send these to OpenTelemetry, LangSmith, or Langfuse.
Here we capture to a list in memory (or optionally to a JSON file) so the
eval suite can inspect exactly what the Model received and what it did.

Every agent run produces a trace. Every eval attaches a score to a trace ID.
A failing eval without a trace is a number you cannot act on.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Trace:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_version: str = ""
    transaction_id: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    steps: list = field(default_factory=list)
    final_decision: Optional[str] = None
    eval_scores: dict = field(default_factory=dict)

    def add_step(self, step: dict):
        self.steps.append({**step, "step_index": len(self.steps)})

    def complete(self, decision: str):
        self.final_decision = decision
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def attach_score(self, eval_name: str, score: float, passed: bool, reason: str = ""):
        self.eval_scores[eval_name] = {
            "score": score,
            "passed": passed,
            "reason": reason
        }

    def tool_calls(self) -> list:
        return [s for s in self.steps if s.get("type") == "tool_use"]

    def model_calls(self) -> int:
        return len([s for s in self.steps if s.get("type") == "model_call"])

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "agent_version": self.agent_version,
            "transaction_id": self.transaction_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "model_calls": self.model_calls(),
            "tool_calls": len(self.tool_calls()),
            "tools_used": list({s["tool"] for s in self.tool_calls()}),
            "final_decision": self.final_decision,
            "eval_scores": self.eval_scores,
            "steps": self.steps
        }

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "Trace":
        with open(path) as f:
            data = json.load(f)
        t = cls()
        t.trace_id = data["trace_id"]
        t.agent_version = data.get("agent_version", "")
        t.transaction_id = data.get("transaction_id", "")
        t.started_at = data.get("started_at", "")
        t.completed_at = data.get("completed_at")
        t.final_decision = data.get("final_decision")
        t.eval_scores = data.get("eval_scores", {})
        t.steps = data.get("steps", [])
        return t
