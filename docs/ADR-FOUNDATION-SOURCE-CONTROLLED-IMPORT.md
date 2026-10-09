# ADR — Approved Foundation Source Controlled Import

Status: Draft implementation in PR #13  
Date: 2026-10-09

## Decision

Hamoon's human-approved Foundation Behavior source may enter the runtime learning
dataset registry without fabricating operational LearningSignal lineage.

The controlled path is:

```text
Human-approved repository Foundation Source
→ source file SHA-256 attestation
→ explicit ADMIN import
→ DRAFT LearningDatasetVersion
→ independent provenance re-attestation
→ explicit ADMIN Dataset Approval
→ eligible for the existing Internal Training Run path
```

## Provenance model

Runtime datasets distinguish two source kinds:

- `CURATED_LEARNING_SIGNAL` — the existing operational learning path.
- `APPROVED_FOUNDATION_SOURCE` — approved synthetic day-one instruction sources.

Foundation items have no `learning_signal_id`, `signal_type`, or `signal_label`.
They carry an immutable `source_key` plus source refs to the approved repository
dataset, example ID, source SHA-256, and human approval record.

## Safety boundary

Import never approves a runtime Dataset and never starts Training.

Runtime Dataset Approval re-reads and re-attests the repository source and fails
closed if the file digest, source metadata, example order, payload, grounding, or
approval evidence differs.

No operational LearningSignal, household, HumanDecision, Outcome, or Provider
record is fabricated to make synthetic instruction data fit the operational
learning schema.

Training/Evaluation separation and explicit model promotion remain unchanged.

## Scope

v1 supports only the two human-approved source tasks currently present:

- DIAGNOSIS
- OUTCOME_INTERPRETATION

PRESCRIPTION remains deferred because its target contract contains
policy-bearing `review_schedule` and `success_criteria` fields for which no
authoritative day-one source has been approved.
