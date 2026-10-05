# Hamoon — Core E2E Golden Path

Status: PB-123 acceptance gate implemented.

## Purpose

The core E2E gate proves that Hamoon's existing application/domain handlers compose into the required product chain without introducing a test-only orchestration path.

The gate runs:

```text
Create Household
→ Record + validate Household Fact
→ Human Accepted State resolution
→ Baseline Assessment
→ Record + validate + accept indicator observations
→ Deterministic official PGOR
→ Structured AI Diagnosis proposal
→ Human Diagnosis confirmation
→ Structured AI Prescription proposal
→ Human Prescription approval
→ Activate Intervention
→ Rule-based Provider Match
→ Explicit human Provider selection + Referral creation
→ Referral send with idempotency/data-sharing boundary
→ Provider Result
→ Scheduled Reassessment
→ Reassessment using the original definition_version
→ Record + validate + accept post-intervention observations
→ Deterministic official Post-PGOR
→ Outcome preparation
→ Human Outcome confirmation
→ OUTCOME_OBSERVED Learning Signal
```

## Non-negotiable assertions

The test proves that:

- both pre and post PGOR are calculated by the deterministic PGOR handler from Accepted Observations;
- AI does not choose the Provider;
- Provider selection is represented by an explicit HumanDecision created by the referral path;
- Provider Result exists separately from Hamoon Outcome;
- reassessment retains the baseline assessment's exact definition version;
- Outcome is based on official pre/post snapshots;
- the human Outcome payload preserves `causal_claim=false`;
- the resulting Learning Signal references the Outcome and Provider Result;
- the Prescription DecisionTrace links intervention, referral, provider result and outcome.

## Test boundary

The core E2E test uses in-memory repository implementations so the acceptance gate isolates business/application composition and runs deterministically in CI. It still calls the production handlers and policies; it does not reimplement PGOR, AI review, Provider selection, Referral, reassessment or Outcome logic.

This is intentionally complementary to, not a replacement for:

- PostgreSQL/MinIO/NATS integration tests;
- immutable-image release smoke;
- Stage Admission using the promoted images;
- Recovery Rehearsal.

Those gates prove infrastructure and artifact boundaries separately.

## CI

The quality job runs:

```text
pytest tests/unit/operations/test_core_e2e_golden_path.py
pytest tests/unit/operations/test_reassessment_learning_loop_golden_path.py
```

The first gate covers the complete PB-123 product path. The second keeps the deeper Outcome-learning/curation regression path independently protected.
