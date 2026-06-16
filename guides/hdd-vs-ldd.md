# Harness-Driven Design vs. LLM-Driven Design

![ADD — HDD vs LLMDD](../img/add-hdd-llmdd.png)

Every improvement to an agent is either a Harness change or a Model change. Knowing which one to make — and in what order — is the core design skill in ADD.

---

## The two design modes

### Harness-Driven Design (HDD)

**When the problem is in the Harness.**

The Model is reasoning correctly given what it receives. The problem is in what it receives, what tools it has, or how outputs are handled.

```
Model (unchanged) → better Harness → better Agent
```

**Symptoms:**
- Wrong or missing context in the prompt
- Poor routing or orchestration decisions
- Missing, poorly defined, or incorrectly scoped tools
- Bad memory or state handling across turns
- Prompt quality issues — vague instructions, missing constraints

**Response:**
- Keep the Model constant
- Improve prompts, tools, context construction, routing rules
- Fix memory retrieval, guardrails, output validation

**Goal:** Work around the Model's limitations. Make the agent smarter without touching the Model.

---

### LLM-Driven Design (LLMDD)

**When the problem is in the Model.**

The Harness is giving the Model the right context, the right tools, and the right instructions — and the Model still produces wrong outputs. The failure is in the Model's reasoning, knowledge, or behavior.

```
Harness (unchanged) → better Model → better Agent
```

**Symptoms:**
- Hallucinations or factually wrong answers despite correct context
- Fails complex multi-step instructions that are clearly stated
- Inconsistent behavior on the same input across runs
- Low quality scores on evals after Harness is already optimized
- Domain vocabulary the base model does not know reliably

**Response:**
- Keep the Harness constant
- Try a better base model, or fine-tune on the specific failure mode
- Evaluate reasoning quality, not just output format

**Goal:** Improve the brain. Make the Model stronger for this specific context.

---

## The decision rule

```
Eval fails
    │
    ├── Is the Model receiving the right context, tools, and instructions?
    │       NO → Harness problem → HDD
    │
    └── Is the Model receiving everything correctly but still failing?
            YES → Model problem → LLMDD
                  (only after HDD has been exhausted)
```

**HDD is the default.** Most agent failures are Harness failures. Go to LLMDD only after HDD has been fully explored — because Harness changes are faster, cheaper, and reversible. Fine-tuning is expensive and couples the Model to the current Harness.

---

## The improvement cycle

```
Observe          Hypothesize       Choose path      Iterate
(evals, traces)  (HDD or LLMDD?)     (HDD or LLMDD)     (small changes)
      │                │                 │                │
      └────────────────┴─────────────────┴────────────────┘
                                                          │
                                                    Measure
                                                 (improve or pivot)
                                                          │
                                                       Repeat
```

1. **Observe** — run evals, read traces. Identify exactly where the failure occurs.
2. **Hypothesize** — is this a context problem (HDD) or a reasoning problem (LLMDD)?
3. **Choose path** — commit to one. Do not change Model and Harness simultaneously.
4. **Iterate** — make small, targeted changes.
5. **Measure** — re-run evals. Did the score improve?
6. **Repeat** — if improved, continue. If not, reconsider the hypothesis.

Changing Model and Harness at the same time makes it impossible to know which change caused the improvement or regression.

---

## How HDD and LLMDD fit into ADD

```
ADD
├── Agent = Model + Harness          ← the fundamental unit
├── Harness-Driven Design (HDD)      ← when the problem is in the Harness
└── LLM-Driven Design (LLMDD)          ← when the problem is in the Model
```

ADD defines the architecture. HDD and LLMDD define the design strategies for improving it. Every agent improvement is one or the other — never both at once.

---

## At a glance

| | HDD | LLMDD |
|---|---|---|
| **Problem is in** | Harness | Model |
| **What you change** | Prompts, tools, routing, memory, context | Model version, fine-tuning |
| **What stays fixed** | Model | Harness |
| **When to use** | Default — try first | After HDD is exhausted |
| **Cost** | Low — code changes | High — training cost, coupling risk |
| **Reversibility** | High | Low |

---

## Worked example: Credit Card Fraud Agent

A Fraud Agent evaluates transactions and decides whether to block a card. The team runs evals and scores are low. Here is how they apply the HDD → LLMDD cycle.

---

### The agent (starting point)

```python
# Harness: system prompt
SYSTEM = "You are a fraud detection agent. Analyze the transaction and decide: APPROVE or BLOCK."

# Harness: tool surface
TOOLS = [
    {"name": "get_transaction", "description": "Get transaction details by ID."},
]

# Harness: agentic loop
def run_fraud_agent(transaction_id: str) -> str:
    messages = [{"role": "user", "content": f"Evaluate transaction {transaction_id}."}]
    # ... loop, tool calls, return decision
```

**Eval result:** 61% accuracy. The agent blocks legitimate transactions and approves suspicious ones.

---

### Round 1 — HDD

**Observe:** Read the traces. The Model is calling `get_transaction` and receiving the data correctly — but it only sees the current transaction. It has no velocity context (how many transactions this card made in the last hour) and no merchant risk profile.

**Hypothesize:** The Model is reasoning from incomplete context. This is a Harness problem — missing tools and missing context injection.

**HDD changes (Model unchanged):**

```python
# Added tools
TOOLS = [
    {"name": "get_transaction",      "description": "Get transaction details by ID."},
    {"name": "get_velocity",         "description": "Get transaction count for this card in the last 60 minutes."},
    {"name": "get_merchant_risk",    "description": "Get risk score and chargeback rate for this merchant."},
    {"name": "get_cardholder_profile","description": "Get typical spend pattern for this cardholder."},
]

# Improved system prompt — explicit decision criteria
SYSTEM = """You are a fraud detection agent. Evaluate the transaction and output APPROVE or BLOCK.

Use the available tools to gather:
1. Transaction details
2. Velocity (transactions in the last 60 minutes on this card)
3. Merchant risk score
4. Cardholder's typical spend pattern

Block if: velocity > 5 in 60 min, OR merchant chargeback rate > 3%, OR amount > 3x typical spend.
Approve otherwise. Output your reasoning before the decision."""
```

**Measure:** Accuracy rises from 61% to 84%. Most false positives are gone.

---

### Round 2 — HDD again

**Observe:** The remaining 16% failures are concentrated on one pattern: cross-border transactions for cardholders who travel frequently. The agent blocks these even when the cardholder has a history of international spending.

**Hypothesize:** The cardholder profile tool does not return travel history. Another Harness gap.

**HDD change:**

```python
# Updated tool — richer cardholder context
{"name": "get_cardholder_profile",
 "description": "Get typical spend pattern, average transaction amount, and travel history (countries visited in last 12 months)."},
```

**Measure:** Accuracy rises to 91%. False positives on international transactions drop by 80%.

---

### Round 3 — LLMDD

**Observe:** The remaining 9% failures are structurally different. The Model receives correct, complete context — all tools called, all data present in the trace — but its reasoning is inconsistent. For the same transaction profile, it sometimes outputs APPROVE and sometimes BLOCK. The inconsistency is not in the data; it is in the Model's judgment.

**Hypothesize:** This is a Model problem. The Harness is providing everything correctly. The base model lacks reliable calibration for fraud decision-making under ambiguity.

**LLMDD change:**

1. Export 300 traces where the correct decision is known (from human review).
2. Filter to the ambiguous cases — the ones the Model gets inconsistently.
3. Fine-tune on `(full_prompt_with_tool_results, correct_decision)` pairs.
4. Keep the Harness identical — same tools, same system prompt, same loop.

```python
# Only this line changes in the Harness
MODEL = "fraud-agent-ft-v1"  # fine-tuned on 300 labeled traces
```

**Measure:** Accuracy rises from 91% to 97%. Inconsistency on ambiguous transactions drops to near zero.

---

### What the cycle looked like

```
Start:  61% accuracy
  │
  ├── HDD Round 1: add velocity + merchant risk + cardholder tools, improve prompt
  │     → 84% (+23pp) — missing context was the problem
  │
  ├── HDD Round 2: add travel history to cardholder profile tool
  │     → 91% (+7pp) — still a Harness gap
  │
  └── LLMDD: fine-tune on 300 labeled ambiguous traces (Harness unchanged)
        → 97% (+6pp) — Model calibration was the remaining problem
```

HDD solved 30 percentage points. LLMDD solved the last 6 — but only after HDD had nothing left to give.

---

### Key lessons from this example

- **Never go to LLMDD first.** The team could have fine-tuned immediately after 61% accuracy. They would have trained a model on incomplete context, embedded a brittle 61%-accuracy Harness into the weights, and created a fine-tuned model that is now hard to improve without retraining.
- **Traces are the diagnostic tool.** Every HDD hypothesis came from reading what the Model actually received, not guessing what it might be missing.
- **LLMDD is scoped to the failure mode.** The fine-tuning dataset was 300 ambiguous traces — not all traces. LLMDD precision matters as much as HDD precision.
- **Change one thing at a time.** Each round changed either the Harness or the Model — never both. This made it possible to attribute each accuracy gain.

---

**Remember:** Start with what you can control. Make it work. Then make the Model stronger.

See also: [How Everything Connects](./how-everything-connects.md) · [Fine-Tuning in ADD](../production/fine-tuning/README.md) · [Evals in ADD](../production/evals/README.md)
