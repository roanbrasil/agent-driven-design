"""
Domain models for the ADD reference system.

All data structures that cross agent boundaries live here.
These are Agent Contracts — the formal interface between agents.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Transaction:
    transaction_id: str
    card_id: str
    amount: float
    merchant_id: str
    merchant_category: str
    country: str
    timestamp: str


@dataclass
class CardProfile:
    card_id: str
    cardholder_name: str
    typical_spend_amount: float
    home_country: str
    active_travel_countries: list[str] = field(default_factory=list)
    account_age_days: int = 0


@dataclass
class VelocityData:
    card_id: str
    transactions_last_60_min: int
    transactions_last_24_hours: int
    velocity_threshold_60_min: int = 5
    velocity_threshold_24_hours: int = 20


@dataclass
class MerchantRisk:
    merchant_id: str
    chargeback_rate: float
    risk_tier: str  # LOW, MEDIUM, HIGH
    chargeback_threshold: float = 0.03


@dataclass
class FraudDecision:
    transaction_id: str
    decision: str  # APPROVE or BLOCK
    reasoning: str
    confidence: float  # 0.0 to 1.0
    signals_used: list[str] = field(default_factory=list)


@dataclass
class EvalCase:
    case_id: str
    description: str
    transaction: Transaction
    card_profile: CardProfile
    velocity: VelocityData
    merchant_risk: MerchantRisk
    expected_decision: str  # APPROVE or BLOCK
    expected_signals: list[str] = field(default_factory=list)
    difficulty: str = "normal"  # easy, normal, hard, edge
