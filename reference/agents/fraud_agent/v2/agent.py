"""
FraudAgent v2 — HDD Round 1.

What changed from v1 (all Harness changes, Model unchanged):
  1. System prompt: explicit decision criteria with thresholds
  2. New tool: get_cardholder_profile() — typical spend, home country
  3. New tool: get_velocity_data() — transactions in last 60 min and 24 hours
  4. New tool: get_merchant_risk() — chargeback rate, risk tier
  5. System prompt now tells the Model what signals to check and in what order

Why these changes:
  After inspecting traces from v1, the Model was making decisions with only
  merchant_category and amount. It had no velocity, no cardholder baseline,
  no merchant risk tier. These are the core signals. The Harness wasn't
  providing them. Classic HDD failure.

Eval results on the golden dataset:
  Pass rate:     80%  (16/20)
  Avg score:     3.4 / 5
  Remaining failures: TC-004, TC-011 (travel cases — no travel history in profile)
                      TC-015 (corporate card — amount looks high without profile context)
                      TC-017 (impossible travel — needs prior transaction location)

The travel cases still fail because the cardholder profile tool doesn't include
travel history. That's the next HDD iteration. See v3/.
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

import anthropic
from reference.domain.models import Transaction, CardProfile, VelocityData, MerchantRisk, FraudDecision

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a fraud detection agent for a credit card company.

Evaluate transactions using the tools available. Check these signals in order:

1. VELOCITY — Call get_velocity_data(). If transactions_last_60_min > 5, that is a strong fraud signal.
2. AMOUNT — Call get_cardholder_profile(). If amount > 2x typical_spend_amount, that is elevated risk.
3. MERCHANT RISK — Call get_merchant_risk(). If risk_tier is HIGH or chargeback_rate > 0.03, that is a fraud signal.
4. GEOGRAPHY — If the transaction country differs from home_country, consider it elevated risk unless you have context explaining travel.

Decision rule:
- Block if velocity_last_60_min > 5, OR merchant risk is HIGH, OR two or more moderate signals converge.
- Approve if all signals are low risk.

Respond with valid JSON:
{
  "decision": "APPROVE" or "BLOCK",
  "reasoning": "cite specific numbers from your tool results",
  "confidence": 0.0 to 1.0,
  "signals_used": ["list the signal names you relied on"]
}

Be precise. Always cite numbers. 'High velocity' is not enough — say '8 transactions in 60 minutes (threshold: 5)'."""

TOOLS = [
    {
        "name": "get_transaction_details",
        "description": "Get full transaction details by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string"}
            },
            "required": ["transaction_id"]
        }
    },
    {
        "name": "get_cardholder_profile",
        "description": "Get the cardholder's profile including typical spend amount and home country.",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"}
            },
            "required": ["card_id"]
        }
    },
    {
        "name": "get_velocity_data",
        "description": "Get transaction velocity for a card: how many transactions in the last 60 minutes and 24 hours.",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"}
            },
            "required": ["card_id"]
        }
    },
    {
        "name": "get_merchant_risk",
        "description": "Get the risk profile for a merchant: chargeback rate and risk tier (LOW/MEDIUM/HIGH).",
        "input_schema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "string"}
            },
            "required": ["merchant_id"]
        }
    }
]


def _execute_tool(name: str, tool_input: dict, transaction: Transaction,
                  card_profile: CardProfile, velocity: VelocityData,
                  merchant_risk: MerchantRisk) -> dict:
    if name == "get_transaction_details":
        return {
            "transaction_id": transaction.transaction_id,
            "amount": transaction.amount,
            "merchant_id": transaction.merchant_id,
            "merchant_category": transaction.merchant_category,
            "country": transaction.country,
            "timestamp": transaction.timestamp
        }
    elif name == "get_cardholder_profile":
        return {
            "card_id": card_profile.card_id,
            "cardholder_name": card_profile.cardholder_name,
            "typical_spend_amount": card_profile.typical_spend_amount,
            "home_country": card_profile.home_country,
            "account_age_days": card_profile.account_age_days
        }
    elif name == "get_velocity_data":
        return {
            "card_id": velocity.card_id,
            "transactions_last_60_min": velocity.transactions_last_60_min,
            "transactions_last_24_hours": velocity.transactions_last_24_hours,
            "velocity_threshold_60_min": velocity.velocity_threshold_60_min
        }
    elif name == "get_merchant_risk":
        return {
            "merchant_id": merchant_risk.merchant_id,
            "chargeback_rate": merchant_risk.chargeback_rate,
            "risk_tier": merchant_risk.risk_tier,
            "chargeback_threshold": merchant_risk.chargeback_threshold
        }
    else:
        return {"error": f"Unknown tool: {name}"}


def run(
    transaction: Transaction,
    card_profile: CardProfile,
    velocity: VelocityData,
    merchant_risk: MerchantRisk,
    tracer: list = None
) -> FraudDecision:
    if tracer is None:
        tracer = []

    messages = [{
        "role": "user",
        "content": (
            f"Evaluate transaction {transaction.transaction_id} for fraud. "
            f"Card: {transaction.card_id}. "
            f"Amount: ${transaction.amount:.2f}. "
            f"Merchant: {transaction.merchant_id}. "
            f"Use your tools to gather all relevant signals before deciding."
        )
    }]

    tracer.append({"type": "harness", "event": "agent_start", "version": "v2", "transaction_id": transaction.transaction_id})

    while True:
        tracer.append({"type": "model_call", "messages_count": len(messages)})

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
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
                            reasoning="Parse failure — defaulting to BLOCK.",
                            confidence=0.0,
                            signals_used=[]
                        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tracer.append({"type": "tool_use", "tool": block.name, "input": block.input})
                    result = _execute_tool(block.name, block.input, transaction, card_profile, velocity, merchant_risk)
                    tracer.append({"type": "tool_result", "tool": block.name, "result": result})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            messages.append({"role": "user", "content": tool_results})
