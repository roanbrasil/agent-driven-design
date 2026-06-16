"""
FraudAgent v1 — Baseline Harness.

This is where every agent starts: a minimal system prompt, a single tool,
and hope. The Model is asked to make fraud decisions with almost no context.

Eval results on the golden dataset:
  Pass rate:     55%  (11/20)
  Avg score:     2.1 / 5
  Main failures: TC-004, TC-011, TC-015 (legitimate travel blocked)
                 TC-007, TC-020 (edge cases decided wrong way)
                 TC-017 (impossible travel not detected)

This version fails primarily because:
  - The Harness provides only the transaction amount and merchant category.
  - The Model has no velocity data, no cardholder profile, no merchant risk.
  - Without context, the Model guesses. It guesses conservatively (blocks too much)
    but still misses obvious fraud signals.

This is a Harness failure. The Model is capable — it just has nothing to work with.
Fix: HDD (see v2/).
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

import anthropic
from reference.domain.models import Transaction, CardProfile, VelocityData, MerchantRisk, FraudDecision

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a fraud detection agent for a credit card company.

Your job is to evaluate transactions and decide: APPROVE or BLOCK.

You will receive transaction details. Make your best judgment.

Always respond with valid JSON:
{
  "decision": "APPROVE" or "BLOCK",
  "reasoning": "brief explanation",
  "confidence": 0.0 to 1.0,
  "signals_used": ["list", "of", "signals"]
}"""

TOOLS = [
    {
        "name": "get_transaction_details",
        "description": "Get the full details of a transaction by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "string",
                    "description": "The transaction ID to look up."
                }
            },
            "required": ["transaction_id"]
        }
    }
]


def get_transaction_details(transaction_id: str, transaction: Transaction) -> dict:
    return {
        "transaction_id": transaction.transaction_id,
        "amount": transaction.amount,
        "merchant_category": transaction.merchant_category,
        "country": transaction.country,
        "timestamp": transaction.timestamp
    }


def run(
    transaction: Transaction,
    card_profile: CardProfile,
    velocity: VelocityData,
    merchant_risk: MerchantRisk,
    tracer: list = None
) -> FraudDecision:
    """
    Harness entry point. The Model only receives what the Harness decides to give it.
    In v1, the Harness provides almost nothing — this is the baseline.
    """
    if tracer is None:
        tracer = []

    initial_message = f"Evaluate this transaction for fraud risk: transaction_id={transaction.transaction_id}"

    messages = [{"role": "user", "content": initial_message}]

    tracer.append({"type": "harness", "event": "agent_start", "version": "v1", "transaction_id": transaction.transaction_id})

    while True:
        tracer.append({"type": "model_call", "messages_count": len(messages)})

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        tracer.append({"type": "model_response", "stop_reason": response.stop_reason})

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    try:
                        data = json.loads(block.text)
                        return FraudDecision(
                            transaction_id=transaction.transaction_id,
                            decision=data["decision"],
                            reasoning=data["reasoning"],
                            confidence=data.get("confidence", 0.5),
                            signals_used=data.get("signals_used", [])
                        )
                    except (json.JSONDecodeError, KeyError):
                        return FraudDecision(
                            transaction_id=transaction.transaction_id,
                            decision="BLOCK",
                            reasoning="Failed to parse model output — defaulting to BLOCK.",
                            confidence=0.0,
                            signals_used=[]
                        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tracer.append({"type": "tool_use", "tool": block.name, "input": block.input})

                    if block.name == "get_transaction_details":
                        result = get_transaction_details(block.input["transaction_id"], transaction)
                    else:
                        result = {"error": f"Unknown tool: {block.name}"}

                    tracer.append({"type": "tool_result", "tool": block.name, "result": result})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            messages.append({"role": "user", "content": tool_results})
