# Hamoon AI Model Selection

**Decision date:** 2026-10-28  
**Status:** Selected for internal offline evaluation; production activation is not approved.

## Decision

Use **Qwen/Qwen3.5-9B** as Hamoon's first internal model for offline evaluation.

The model card identifies a 9B parameter model, lists Apache-2.0 licensing, and documents compatibility with local inference stacks including vLLM and SGLang. Qwen's model materials list Persian among the supported languages. These properties make it a practical first model to evaluate inside Hamoon; they do not establish that it is accurate enough for Hamoon's cases.

- Model: [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- Publisher language coverage: [Qwen3.5 announcement](https://qwen.ai/blog?id=qwen3.5)

## Permitted initial scope

The model may draft summaries and structured suggestions for a caseworker to review. It must not calculate or replace deterministic PGOR, make eligibility decisions, or autonomously approve diagnoses, prescriptions, provider choices, or outcomes.

Household information must remain within Hamoon's internal environment. Do not send it to an external inference API.

## Gate before production

This decision selects the model for evaluation only. The model must remain unavailable to production traffic until all of the following are complete:

1. Pin the imported weight revision and verify its license and artifact hashes.
2. Evaluate with a de-identified, human-reviewed Persian dataset representative of Hamoon's case notes and workflows.
3. Measure factual grounding, structured-output validity, unsupported claims, consistency, Persian/RTL quality, subgroup errors, unsafe recommendations, latency, and resource use.
4. Record evaluation artifacts and lineage in Hamoon's model registry, then require explicit human promotion.
5. Keep the fail-closed path to a Human Work Item enabled whenever inference or validation is unavailable or fails.

The training engine, artifact storage and execution semantics, and internal production executor are still separate deferred decisions.
