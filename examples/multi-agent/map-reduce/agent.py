"""
Multi-Agent Map-Reduce — Anthropic  [ADVANCED]
===============================================
Map-Reduce topology: a Coordinator fans out the same task to N independent
Worker agents (map), then a Reducer aggregates their outputs into a single
final answer (reduce).

Use case: document analysis — each Worker independently analyzes one document,
the Reducer synthesizes all findings.

ADD mapping:
  - Model   : Worker analysis, Reducer synthesis, Coordinator planning
  - Harness : fan-out dispatch, result collection, reduce trigger,
              worker isolation (each Worker is a separate Agent Context Boundary)
  - Infra   : Anthropic API

Key ADD concepts:
  - Map-Reduce topology: all Workers receive the same capability surface
    but operate on different data slices
  - Agent Context Boundaries: Workers don't share context with each other
  - Coordinator is Universal; Workers are Conditional (only run when needed)

This example uses Python threads for concurrent Worker calls.
In production, use asyncio or a task queue.

Run:
    pip install -r requirements.txt
    cp .env.example .env
    python agent.py
"""

import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"

# ── Harness: sample documents ─────────────────────────────────────────────────
DOCUMENTS = [
    {
        "id": "doc-1",
        "title": "Q3 Revenue Report",
        "content": (
            "Revenue reached $4.2M in Q3, up 18% year-over-year. "
            "SaaS subscriptions grew 32% driven by enterprise segment. "
            "Churn rate increased slightly to 3.1% due to SMB losses. "
            "Operating costs rose 12%, keeping EBITDA margin at 22%."
        ),
    },
    {
        "id": "doc-2",
        "title": "Customer Satisfaction Survey",
        "content": (
            "NPS score dropped from 62 to 54 this quarter. "
            "Top complaints: onboarding complexity (38%), slow support response (29%). "
            "Promoters cite product reliability and API quality as key strengths. "
            "Enterprise customers rate us 8.2/10; SMB customers 6.7/10."
        ),
    },
    {
        "id": "doc-3",
        "title": "Engineering Incident Report",
        "content": (
            "Three P1 incidents in Q3 totaling 4.5 hours of downtime. "
            "Root causes: database connection pool exhaustion (2x), CDN misconfiguration (1x). "
            "Mean time to recovery improved to 87 minutes from 134 minutes last quarter. "
            "Post-mortems completed; circuit breakers added to payment service."
        ),
    },
    {
        "id": "doc-4",
        "title": "Sales Pipeline Summary",
        "content": (
            "Pipeline value at $8.1M, conversion rate 23% (up from 19%). "
            "Average deal size grew to $41k driven by multi-year contracts. "
            "47 new enterprise prospects added. "
            "Top lost-deal reason: pricing (41%), followed by competitor features (28%)."
        ),
    },
]

# ── Harness: Worker system prompt ─────────────────────────────────────────────
WORKER_SYSTEM = """You are a business analyst. Analyze the document provided and extract:
1. Key metrics (numbers, percentages, KPIs)
2. Main risks or problems identified
3. Positive signals or opportunities
4. One-sentence executive summary

Respond ONLY with a JSON object:
{
  "doc_id": "...",
  "metrics": ["metric 1", "metric 2"],
  "risks": ["risk 1"],
  "opportunities": ["opportunity 1"],
  "summary": "One sentence."
}"""

# ── Harness: Reducer system prompt ────────────────────────────────────────────
REDUCER_SYSTEM = """You are an executive analyst. You will receive structured analyses
of multiple business documents. Synthesize them into a coherent executive briefing.

Cover:
- Overall business health (2-3 sentences)
- Top 3 risks that need immediate attention
- Top 3 opportunities to pursue
- Recommended priority actions (bullet points)

Be direct and concise. Executives have 2 minutes to read this."""


# ── Harness: Worker agent (MAP phase) ────────────────────────────────────────
def worker_analyze(doc: dict) -> dict:
    """
    ADD: Each Worker has its own isolated context boundary.
    Workers don't know about each other — isolation is a Harness guarantee.
    """
    prompt = f"Title: {doc['title']}\n\nContent:\n{doc['content']}"
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=WORKER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    try:
        result = json.loads(text)
        result["doc_id"] = doc["id"]
        result["title"] = doc["title"]
        return result
    except json.JSONDecodeError:
        return {"doc_id": doc["id"], "title": doc["title"], "raw": text, "error": "parse_failed"}


# ── Harness: Reducer agent (REDUCE phase) ─────────────────────────────────────
def reducer_synthesize(analyses: list[dict]) -> str:
    """
    ADD: Reducer receives all Worker outputs collected by the Harness.
    This is the only Model call that sees across document boundaries.
    """
    analyses_text = json.dumps(analyses, indent=2, ensure_ascii=False)
    prompt = f"Here are the analyses of {len(analyses)} business documents:\n\n{analyses_text}\n\nProvide the executive briefing."
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=REDUCER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── Harness: map-reduce orchestration ────────────────────────────────────────
def run_map_reduce(documents: list[dict], max_workers: int = 4) -> str:
    """
    ADD: The Harness fans out to Workers concurrently (map),
    collects all results, then calls the Reducer (reduce).
    Workers are isolated — none sees another's output until the Reducer.
    """
    print(f"[Map phase] Analyzing {len(documents)} documents concurrently...\n")

    # ── MAP: fan-out to Workers in parallel ───────────────────────────────────
    analyses = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(worker_analyze, doc): doc["id"] for doc in documents}
        for future in as_completed(futures):
            doc_id = futures[future]
            result = future.result()
            analyses.append(result)
            summary = result.get("summary", result.get("raw", "")[:80])
            print(f"  ✓ {doc_id} ({result.get('title', '')}): {summary}")

    # Sort to keep output deterministic
    analyses.sort(key=lambda x: x["doc_id"])

    # ── REDUCE: aggregate all Worker outputs ──────────────────────────────────
    print(f"\n[Reduce phase] Synthesizing {len(analyses)} analyses...\n")
    return reducer_synthesize(analyses)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Map-Reduce Agent — Business Document Analysis")
    print("=" * 60)
    final = run_map_reduce(DOCUMENTS)
    print(f"\n{'='*60}\nEXECUTIVE BRIEFING\n{'='*60}\n{final}")
