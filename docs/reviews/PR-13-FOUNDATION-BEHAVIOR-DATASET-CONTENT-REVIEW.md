# PR #13 — Foundation Behavior Dataset v1 — Content Review

Status: **Reviewed + Human-approved source / Draft remains open**

Reviewed HEAD before fixes: `e5c3d310cb7948ec030352c3b073e2992e02912b`

## Scope reviewed

- `training/foundation/v1/behavior_contract.json`
- `training/foundation/v1/diagnosis.json`
- `training/foundation/v1/outcome_interpretation.json`
- existing Diagnosis / Outcome AI schemas and runtime guardrails
- current PGOR data-quality vocabulary
- separation from existing evaluation datasets

## Findings

### RESOLVED — invented review-flag vocabulary

Two Diagnosis examples introduced non-canonical review flags:

- `AUTHORITATIVE_PGOR_PRESERVED`
- `DATA_QUALITY_REVIEW_REQUIRED`

No approved registry for those values exists. They were removed. Foundation Diagnosis examples now use only the existing required flag:

`HUMAN_REVIEW_REQUIRED`

### RESOLVED — synthetic non-canonical PGOR quality flag

One example used `FOUNDATION_UNSPECIFIED_REVIEW_FLAG`. The current PGOR implementation emits the canonical flag `HAS_UNRESOLVED_OBSERVATION`.

The example was changed to the canonical flag and now teaches only the permitted behavior: preserve uncertainty and do not infer the unresolved observation's value, direction, or effect.

### RESOLVED — impossible authoritative-bottleneck example

One example intentionally supplied numeric PGOR values inconsistent with its authoritative bottleneck list. That is not representative of the deterministic PGOR engine contract.

The example was corrected to a consistent Feature Package while preserving the intended lesson: AI consumes the authoritative bottleneck output and does not recalculate or rewrite PGOR.

## No-blocker findings

- No production household data is present.
- No hidden chain-of-thought target is present.
- Outcome examples keep `causal_claim=false`.
- Provider Result is not treated as Hamoon Outcome.
- No Provider selection or Referral dispatch is taught.
- Prescription remains deferred because authoritative policy-bearing values for `review_schedule` and `success_criteria` are not supplied.
- The source pack remains `DRAFT_SOURCE_ONLY / NOT_APPROVED`; it is not runtime-training eligible and does not fabricate LearningSignal lineage.

## Approval boundary

This review does **not** approve the Dataset for training and does not authorize model training, evaluation, promotion, Stage, Release, or Production.


## Human approval record

On 2026-10-09, explicit human approval was provided for the Foundation Behavior Dataset v1 source content.

This approval closes the content-approval gate for the repository source pack only. The runtime governance boundary remains unchanged: no runtime LearningDatasetVersion has been created or approved, no TrainingRun is authorized by this record, and no merge or deployment is implied.
