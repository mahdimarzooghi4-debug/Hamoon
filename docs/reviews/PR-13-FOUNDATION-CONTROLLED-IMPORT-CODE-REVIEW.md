# PR #13 — Foundation Controlled Import — Technical Code Review

Status: **Reviewed / hardening fixes applied / Draft remains open**  
Reviewed HEAD: `04ccc17136201aff19092b67e70a09d1d1a1a13f`  
Date: 2026-10-09

## Review scope

- approved Foundation source packaging
- runtime controlled import
- provenance model and database constraints
- source re-attestation before Dataset Approval
- compatibility with the existing Internal Training Run
- separation from operational LearningSignal provenance
- Docker/runtime availability of source evidence
- no auto-approval, auto-training, auto-promotion, or Production side effect

## Finding 1 — RESOLVED: task status disagreed with pack approval

The pack manifest was `APPROVED_SOURCE_ONLY`, while the task files still
declared `DRAFT_SOURCE_ONLY`.

Both task sources now declare `APPROVED_SOURCE_ONLY`, and the runtime loader
fails closed unless the task file itself has that exact status.

## Finding 2 — RESOLVED: source digest covered only the task JSON

The first controlled-import implementation hashed only the task JSON. That
would detect example drift, but it did not pin the full human-approved evidence
package.

The source digest now covers, in deterministic order:

- `manifest.json`
- `behavior_contract.json`
- the selected task JSON
- the human approval record under `docs/approvals`

The Production/runtime image now includes both `training/` and
`docs/approvals/`, so re-attestation can be performed from the exact deployed
application artifact without network access.

A regression test verifies that changing the approval evidence changes the
source digest.

## Training compatibility

The existing Internal Training Run consumes only each Dataset item's
`input_payload` and `target_payload`. It does not require
`learning_signal_id`, `signal_type`, or `signal_label` at execution time.

Therefore Foundation items can correctly carry independent source provenance
without fabricating operational LearningSignal records.

## Governance result

No blocker remains in the reviewed Controlled Import design.

The path remains:

```text
Human-approved Foundation Source
→ package SHA-256 attestation
→ explicit ADMIN import
→ DRAFT LearningDatasetVersion
→ package re-attestation
→ explicit ADMIN Dataset Approval
→ existing governed Internal Training Run
```

Import does not approve the Dataset, start Training, run Evaluation, create a
Candidate, activate a Routing Policy, merge the PR, or deploy Production.
