"""
FraudAgent v3 — HDD Round 2.

What changed from v2 (all Harness changes, Model unchanged):
  1. get_cardholder_profile() now includes active_travel_countries
  2. System prompt updated: explicit travel exception rule
  3. System prompt updated: corporate card detection (typical_spend > $1000)
  4. New decision criterion: if country in active_travel_countries → geography signal clears

Why these changes:
  After v2, we inspected the 4 remaining failures. Three of them (TC-004, TC-011, TC-015)
  shared a pattern: legitimate cardholders blocked because the Harness wasn't providing
  travel context. The fix is straightforward — the data exists in the cardholder database,
  the Harness just wasn't fetching it. Another Harness failure.

  TC-017 (impossible travel) still requires checking prior transaction location which
  would need a new data source. That's a separate HDD ticket.

Eval results on the golden dataset:
  Pass rate:     90%  (18/20)
  Avg score:     4.1 / 5
  Remaining failures: TC-017 (impossible travel — needs prior tx location data)
                      TC-020 (borderline edge case — multiple moderate signals)

At 90% pass rate, the remaining 2 failures are edge cases with missing data (TC-017)
or genuine ambiguity (TC-020). Before going to LLMDD, the next HDD move would be
to add a get_recent_transactions() tool to detect impossible travel patterns.

If that doesn't close the gap further, or if the Model is making qualitatively
wrong decisions despite having all the right context, that's the signal for LLMDD.
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

1. VELOCITY — Call get_velocity_data(). Block if transactions_last_60_min > 5.

2. AMOUNT — Call get_cardholder_profile(). Elevated risk if amount > 2x typical_spend_amount.
   Exception: if typical_spend_amount > $1000 (corporate card), use $5000 as the threshold.

3. MERCHANT RISK — Call get_merchant_risk(). Block if risk_tier is HIGH or chargeback_rate > 0.03.

4. GEOGRAPHY — If transaction country differs from home_country:
   - Call get_cardholder_profile() and check active_travel_countries.
   - If transaction country is in active_travel_countries → geography signal clears (legitimate travel).
   - If transaction country is NOT in active_travel_countries → elevated risk signal.

Decision rule:
- Block if: velocity_last_60_min > 5
            OR merchant risk tier is HIGH
            OR chargeback_rate > 0.03
            OR two or more of [amount_elevated, geography_risk, medium_merchant_risk] converge.
- Approve if: all signals are clear, OR only one moderate signal with travel explanation.

Respond with valid JSON:
{
  "decision": "APPROVE" or "BLOCK",
  "reasoning": "cite specific numbers. e.g. '8 transactions in 60 min (threshold: 5)'",
  "confidence": 0.0 to 1.0,
  "signals_used": ["signal_name_1", "signal_name_2"]
}"""

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
        "description": "Get the cardholder profile: typical spend, home country, and active travel countries.",
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
        "description": "Get transaction velocity: count in last 60 minutes and 24 hours, with thresholds.",
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
        "description": "Get merchant risk profile: chargeback rate and risk tier (LOW/MEDIUM/HIGH).",
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
            "active_travel_countries": card_profile.active_travel_countries,
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
            f"Amount: ${transaction.amount:.2f} at {transaction.merchant_category} merchant. "
            f"Country: {transaction.country}. "
            f"Use all available tools before deciding."
        )
    }]

    tracer.append({"type": "harness", "event": "agent_start", "version": "v3", "transaction_id": transaction.transaction_id})

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
