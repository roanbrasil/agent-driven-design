# ADD Reference System

A complete, runnable implementation of Agent-Driven Design concepts using a credit card fraud detection domain.

This is the ADD equivalent of the DDD reference application: a real system, not a toy example, that demonstrates every core concept working together.

---

## What this demonstrates

| ADD Concept | Where it appears |
|---|---|
| Agent = Model + Harness | Each `agent.py` file — the Model is one API call; the Harness is everything else |
| Agent Context Boundary | The fraud agent only has tools for its own domain — no payment processing, no card issuance |
| HDD (Harness-Driven Design) | v1 → v2 → v3 progression, with eval scores showing the Harness improvement |
| LLMDD decision point | Documented in v3 agent and in `compare_versions.py` output |
| Agent Contract | `domain/models.py` — all cross-boundary data structures |
| Output evals | `evals/output_eval.py` — did the agent get the right decision? |
| Trajectory evals | `evals/trajectory_eval.py` — did it use the right tools in the right order? |
| LLM-as-Judge | `evals/llm_judge.py` — is the reasoning quality sufficient? |
| Observability | `observability/tracer.py` — every agent run produces a trace |
| Eval-driven development | `evals/runner.py` + `scripts/compare_versions.py` — evals gate every version |

---

## The domain

A credit card fraud detection system. Three components, each an Agent:

- **FraudAgent** (this reference system): evaluates transactions, returns APPROVE or BLOCK
- **CardAgent** (scope of another agent): owns card profile data — provides it via tool
- **PaymentAgent** (scope of another agent): owns payment authorization — consumes FraudAgent decisions

The FraudAgent's context boundary: it knows about transactions, velocity, cardholder profiles, and merchant risk. It does not know how to process payments. It does not own cardholder account management.

---

## The HDD progression

Three versions of the same FraudAgent, showing Harness-Driven Design in action:

### v1 — Baseline (expected ~55% pass rate)

What the Harness provides:
- Transaction amount, merchant category, country

What it does not provide:
- Velocity data
- Cardholder profile (typical spend, home country)
- Merchant risk tier

What happens: the Model guesses. It guesses conservatively. It still misses obvious fraud patterns because it has no data.

This is not a Model problem. The Model is capable. The Harness is not giving it anything to work with.

### v2 — HDD Round 1 (expected ~80% pass rate)

Harness changes (Model unchanged):
- Added `get_cardholder_profile()` — typical spend, home country
- Added `get_velocity_data()` — transactions in last 60 and 24 hours with thresholds
- Added `get_merchant_risk()` — chargeback rate and risk tier
- System prompt: explicit decision criteria with thresholds and signal priority order

Remaining failures: travel cases. The Harness now provides the right signals for domestic fraud but not for the "legitimate travel" pattern. The cardholder profile exists in the database but the Harness isn't fetching `active_travel_countries`.

### v3 — HDD Round 2 (expected ~90% pass rate)

Harness changes (Model unchanged):
- `get_cardholder_profile()` now returns `active_travel_countries`
- System prompt: explicit travel exception rule
- System prompt: corporate card detection for high-typical-spend profiles

Remaining failures:
- **TC-017**: Impossible travel detection (card used 30 min apart in US and Germany) — needs a `get_recent_transactions()` tool, which would be HDD Round 3
- **TC-020**: Genuine borderline case — multiple moderate signals, no single clear indicator. Human experts disagree on this one.

### When to consider LLMDD

After v3, the right next HDD move is adding `get_recent_transactions()` to close TC-017.

LLMDD becomes the right path when:
1. The Harness is providing all available relevant context
2. The Model is still producing wrong decisions
3. The failure pattern is consistent (not random noise)
4. You have enough labeled examples of the failure (ideally 200+) to fine-tune on

Jumping to LLMDD before exhausting HDD is expensive and often unnecessary. Most agent failures are Harness failures.

---

## Setup

```bash
# From the project root
pip install anthropic

# Set your API key
export ANTHROPIC_API_KEY=your_key_here
```

---

## Running evals

```bash
# Run output + trajectory evals against v3 (all 20 cases)
python reference/scripts/run_evals.py --version v3

# Include LLM-as-Judge (additional API calls to claude-sonnet)
python reference/scripts/run_evals.py --version v3 --judge

# Run specific cases only
python reference/scripts/run_evals.py --version v2 --cases TC-004,TC-011,TC-015

# Save full results with traces for inspection
python reference/scripts/run_evals.py --version v3 --output results_v3.json

# Compare all three versions side by side (60 API calls total)
python reference/scripts/compare_versions.py
```

---

## File map

```
reference/
├── README.md                          (this file)
├── domain/
│   ├── models.py                      Agent Contracts — all data structures
│   └── golden_dataset.json            20 labeled test cases (domain expert labels)
├── agents/
│   └── fraud_agent/
│       ├── v1/agent.py                Baseline Harness — minimal, ~55% pass rate
│       ├── v2/agent.py                HDD Round 1 — velocity + profile + risk, ~80%
│       └── v3/agent.py                HDD Round 2 — travel history added, ~90%
├── evals/
│   ├── runner.py                      Loads dataset, runs all evals, prints summary
│   ├── output_eval.py                 Did the agent get the right decision?
│   ├── trajectory_eval.py             Did it use the right tools correctly?
│   └── llm_judge.py                   Is the reasoning quality sufficient?
├── observability/
│   └── tracer.py                      Trace capture — every run produces a trace
└── scripts/
    ├── run_evals.py                   CLI for single-version eval runs
    └── compare_versions.py            Side-by-side HDD progression comparison
```

---

## The golden dataset

20 labeled cases in `domain/golden_dataset.json`. Each case includes:

- The transaction (amount, merchant, country, timestamp)
- The cardholder profile (typical spend, home country, travel history)
- Velocity data (transactions in last 60 minutes and 24 hours)
- Merchant risk (chargeback rate, risk tier)
- Expected decision (APPROVE or BLOCK), labeled by a domain expert
- Expected signals (which data points justify the decision)
- Difficulty: easy, normal, hard, or edge

Distribution: 8 easy, 7 normal, 3 hard, 2 edge. The edge cases (TC-007, TC-017, TC-020) are intentionally ambiguous or require data not present in v1/v2.

---

## Extending this system

**Add a new eval case**: add an entry to `domain/golden_dataset.json` following the existing schema. Run `python reference/scripts/run_evals.py --version v3 --cases YOUR_CASE_ID` to verify it runs.

**Add HDD round 4**: create `agents/fraud_agent/v4/agent.py`. Add `"v4"` to `REQUIRED_TOOLS_BY_VERSION` in `evals/trajectory_eval.py`. Add a `VERSIONS` entry to `compare_versions.py`.

**Add a new tool**: implement the tool function in the agent file and add it to the `TOOLS` list. Update `REQUIRED_TOOLS_BY_VERSION` in `trajectory_eval.py` so the trajectory eval requires it.

**Use a different model**: change the `model=` parameter in any `agent.py`. The Model is one line in the Harness. Everything else stays the same. This is ADD working as intended.
