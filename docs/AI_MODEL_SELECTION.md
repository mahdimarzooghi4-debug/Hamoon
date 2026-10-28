# Hamoon AI Model Selection

**Decision date:** 2026-10-28  
**Status:** Selected for internal offline evaluation; a local-only structured inference runner is implemented. Production activation is not approved.

## Decision

Use **Qwen/Qwen3.5-9B** as Hamoon's first internal model for offline evaluation.

The model card identifies a 9B parameter model, lists Apache-2.0 licensing, and documents compatibility with local inference stacks including vLLM and SGLang. Qwen's model materials list Persian among the supported languages. These properties make it a practical first model to evaluate inside Hamoon; they do not establish that it is accurate enough for Hamoon's cases.

- Model: [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- Pinned baseline revision: `c202236235762e1c871ad0ccb60c8ee5ba337b9a`
- Publisher language coverage: [Qwen3.5 announcement](https://qwen.ai/blog?id=qwen3.5)

## Permitted initial scope

The runner is limited to case summaries, evidence synthesis, and data-anomaly explanations for offline evaluation. It must not calculate or replace deterministic PGOR, infer missing facts, or generate diagnosis, prescription, provider, eligibility, or outcome decisions. A human must review every draft.

Household information must remain within Hamoon's internal environment. Do not send it to an external inference API.

## Gate before production

This decision selects the model for evaluation only. The model must remain unavailable to production traffic until all of the following are complete:

1. Pin the imported weight revision and verify its license and artifact hashes.
2. Evaluate with a de-identified, human-reviewed Persian dataset representative of Hamoon's case notes and workflows.
3. Measure factual grounding, structured-output validity, unsupported claims, consistency, Persian/RTL quality, subgroup errors, unsafe recommendations, latency, and resource use.
4. Record evaluation artifacts and lineage in Hamoon's model registry, then require explicit human promotion.
5. Keep the fail-closed path to a Human Work Item enabled whenever inference or validation is unavailable or fails.

The local runner accepts only an already provisioned checkpoint directory and an explicitly pinned revision. It does not download model files at runtime, train/fine-tune, create registry lineage, or register itself as a Production executor. A JSONL evaluation driver is available at `scripts/run_qwen35_offline.py`. Dataset preparation, training, evaluation thresholds, lineage registration, and human promotion remain pending.

To use the runner, provision the official checkpoint into a private local directory outside the serving path. Generate `hamoon-revision.txt` and `hamoon-checkpoint-manifest.json` with the attestation utility, then store the printed manifest SHA-256 separately. The runner verifies that digest and every checkpoint file before loading the model. It requires a recent Transformers install and enough local memory for the 9B checkpoint; it never downloads weights.

```bash
export PYTHONPATH=src
export HAMOON_QWEN35_CHECKPOINT_ROOT=/srv/hamoon/models/qwen3.5-9b
python scripts/attest_qwen35_checkpoint.py \
  --checkpoint-root "$HAMOON_QWEN35_CHECKPOINT_ROOT" \
  --revision c202236235762e1c871ad0ccb60c8ee5ba337b9a
export HAMOON_QWEN35_REVISION=c202236235762e1c871ad0ccb60c8ee5ba337b9a
export HAMOON_QWEN35_MANIFEST_SHA256=<printed-64-character-sha256>
python scripts/run_qwen35_offline.py --input offline-evaluation.jsonl
```

Each JSONL request contains `task_class`, `feature_schema_version`, `features`, and `output_schema`; optional fields are `instructions`, `prompt_policy_version`, `output_schema_version`, and `correlation_id`. The driver writes schema-validated output JSONL to stdout and sends only line number/error code diagnostics to stderr.
