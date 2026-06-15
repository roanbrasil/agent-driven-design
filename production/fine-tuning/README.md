# Fine-Tuning in ADD

## The core insight

Fine-tuning is a Harness → Model knowledge transfer.

When you fine-tune a model, you are moving logic that currently lives in the Harness (prompt engineering, examples, instructions, format constraints) into the weights of the Model. The Model no longer needs to be told — it already knows.

This has architectural implications:

| Before fine-tuning | After fine-tuning |
|---|---|
| System prompt contains format instructions | Model produces correct format by default |
| System prompt contains domain examples | Model has domain knowledge in weights |
| Long few-shot prompts | Short or zero-shot prompts |
| Harness parses inconsistent outputs | Model produces consistent structured outputs |

## When fine-tuning makes sense in ADD

Fine-tuning is the right move when:

1. **Format consistency is critical** — the Model produces the right answer but in inconsistent formats that the Harness has to parse defensively
2. **Prompt is too long** — domain knowledge in the prompt is consuming context window that should be available for task context
3. **Latency is constrained** — shorter prompts mean fewer input tokens and lower latency
4. **Domain vocabulary is specialized** — the base model doesn't have reliable knowledge of your domain's terminology
5. **Eval data shows systematic Model errors** — the same wrong reasoning pattern appears repeatedly and cannot be fixed by better prompting

## When fine-tuning does NOT make sense

- When the problem is in the Harness (wrong tools, wrong retrieval, wrong routing)
- When you have fewer than ~100 high-quality examples
- When behavior needs to change frequently (fine-tuned models are harder to update than prompts)
- When a better base model would solve the problem

## Fine-tuning and Agent Context Boundaries

A fine-tuned model is tightly coupled to the Harness that trained it. If you fine-tune on outputs that assume a specific tool surface, the model will behave unexpectedly in a different Harness context.

This means:
- Fine-tuning is always scoped to a specific Agent Context Boundary
- The training data should reflect the actual Harness context the model will run in
- Switching providers or model versions after fine-tuning requires careful eval regression testing

## ADD workflow for fine-tuning

```
1. Run agent evals → identify systematic Model errors
2. Verify error is Model-side (not Harness-side)
3. Collect failing examples from production traces
4. Clean and label: (prompt, expected_output) pairs
5. Fine-tune on the specific failure mode
6. Run the same evals — score must improve
7. Check for regression on passing evals
8. Update Agent Contract documentation (model version, training data version)
```

## Data collection from traces

Because every agent run is traced (see observability), you have a natural source of fine-tuning data: production traces. The Harness constructed the prompt; the Model responded; human feedback or LLM-as-Judge scored the output. Positive-scored traces are training candidates.

This creates a flywheel:
- Production → traces → evals → fine-tuning data → better model → better production behavior → more traces
