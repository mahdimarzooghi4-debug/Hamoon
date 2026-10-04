# Hamoon — Release Approval Gate

Status: Implemented manual governance boundary.

Production authorization is intentionally separated from CI and Stage Admission.
A successful CI run or PASSED Stage Admission is necessary but never sufficient to
authorize Production.

## Manual approval workflow

The `Release Approval` workflow is triggered only through `workflow_dispatch`.
The human approver must provide:

- the exact 40-character commit SHA;
- the exact confirmation text `APPROVE`;
- a change/release/governance reference;
- a human approval rationale.

The workflow rejects bot actors and requires the candidate commit to belong to the
history of `main`.

It then locates a successful Stage Admission for the exact commit, downloads that
Stage attestation, follows it back to the exact source CI run, downloads the immutable
release bundle, and re-verifies both evidence chains before creating approval.

## Approval artifact

A successful manual approval creates:

```text
hamoon-release-approval-<commit-sha>
```

The approval binds:

- commit SHA;
- source CI run;
- Stage Admission run;
- release-manifest SHA-256;
- Stage-attestation SHA-256;
- backend/frontend image IDs;
- GitHub approver identity;
- approval workflow run;
- change reference;
- rationale;
- approval timestamp.

The artifact explicitly records `authorization_only=true` and
`production_deployed=false`. It is permission to proceed to Production deployment,
not proof that Production deployment happened.

## Governance chain

```text
CI SUCCESS
→ immutable verified release bundle
→ Stage Admission PASSED
→ explicit human Release Approval
→ approval artifact
→ Production deployment (separate future gate)
```

No future Production workflow should accept a release unless the corresponding
approval artifact passes `scripts/verify_release_approval.py`.
