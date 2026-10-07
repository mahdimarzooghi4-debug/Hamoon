# Hamoon — Production Deployment Admission Gate

Status: Implemented governance boundary. Hosted deployment execution is implemented through the provider-neutral Production Deploy workflow, but a concrete external orchestrator endpoint/credential is environment-owned.

This gate sits between explicit Release Approval and any provider-specific Production
deployment workflow.

## What it requires

The workflow is manual and requires:

- the exact approved commit SHA;
- explicit `DEPLOY` confirmation;
- a stable Production target identifier;
- a non-local HTTPS Production endpoint;
- an expected runtime deployment identifier;
- a successful immutable Release Approval artifact for the exact commit;
- a successful immutable Production Operational Readiness artifact for the exact commit.

It resolves the Production Operational Readiness and Release Approval artifacts, follows the
approval evidence to the exact Stage Admission and source CI run, downloads the exact release
bundle, and re-verifies the entire governance chain. Readiness must be `READY`, must not claim
deployment, must belong to the same commit, and its immutable SHA-256 is pinned into admission.

## What it produces

A successful admission creates:

```text
hamoon-production-deployment-admission-<commit-sha>
```

The attestation binds the deployment target to:

- commit SHA;
- source CI run;
- Stage Admission run;
- Release Approval run;
- release manifest SHA-256;
- Stage attestation SHA-256;
- Release Approval SHA-256;
- Production Operational Readiness run ID and SHA-256;
- backend/frontend image IDs;
- release approver;
- deployment operator;
- change reference;
- Production target and HTTPS endpoint;
- expected runtime deployment identifier.

The artifact deliberately records `production_deployed=false`.

## Important boundary

This is **not** proof of a Hosted Production deployment. It is the final admission
artifact consumed by the `Production Deploy` workflow before changing Production.
That workflow calls the trusted external HTTPS deployment orchestrator and emits a
separate immutable `hamoon-production-deployment-<sha>` artifact only after the
orchestrator returns a final `DEPLOYED` receipt bound to the exact admitted identities.

## Governance chain

```text
CI
→ immutable release artifact
→ Stage Admission PASSED
→ Production Operational Readiness READY
→ explicit Human Release Approval
→ Production Deployment Admission
→ Production Deploy / trusted external orchestrator
→ immutable Production deployment receipt
→ Production verification
→ Monitoring
```
