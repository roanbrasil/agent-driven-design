# Open Questions

Unresolved questions and gaps in the ADD framework. Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## On the Model/Harness split

**Q: Where does output validation belong when it requires both structural and semantic checking?**
The decision rule says structure → Harness, judgment → Model. But output validation often requires both: check the JSON schema (Harness), then check whether the content makes sense (Model). How should this overlap be formalized?

**Q: Is the decision rule stable across modalities?**
The current rule is defined for text-in / text-out agents. Does it hold for agents that process images, audio, or structured data? What changes?

---

## On Agent Context Boundaries

**Q: How do you draw a boundary when two domains genuinely share state?**
The framework says "one agent writes, others read." But some production systems have legitimate shared ownership (e.g., a fraud signal written by one agent and read by three others as input to different decisions). What is the right pattern?

**Q: Can a boundary span multiple LLMs?**
A single agent boundary might involve a small model for classification and a large model for generation. Is this still one agent? How does the Contract apply?

---

## On topology

**Q: When does Event-Driven (Mesh) topology become preferable to Hierarchical?**
The framework marks Event-Driven as "use sparingly." Are there system properties (scale, dynamism, domain complexity) that make it the correct default?

**Q: What is the right grain for an Orchestrator?**
An Orchestrator that decomposes into 2 workers and one that decomposes into 20 are architecturally different systems. Is there a decomposition limit beyond which the Orchestrator pattern breaks down?

---

## On evals

**Q: How do you eval trajectory, not just output?**
Agent evals that only check final output miss failures in the path (unnecessary tool calls, wrong reasoning steps that reach the right answer). What is the right eval structure for trajectory quality?

**Q: How many LLM-as-Judge calls are needed for reliable scoring?**
A single judge has bias. A panel of 3 judges adds cost. What is the empirically defensible minimum for different task types?

---

## On HDD vs LLMDD

**Q: How do you know when HDD is truly exhausted?**
The framework says "go to LLMDD only after HDD is exhausted." But in practice, it is difficult to prove a negative. What is the operational definition of "HDD exhausted"?

**Q: Does fine-tuning invalidate prior HDD work?**
When you fine-tune (LLMDD), the model now assumes a certain Harness context. If the Harness later changes (HDD), does the fine-tuned model regress? How should this coupling be managed?
