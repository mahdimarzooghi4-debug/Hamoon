# Hamoon — Production Deployment Admission Gate

Status: Implemented governance boundary; Hosted Production is not yet deployed.

This gate sits between explicit Release Approval and any provider-specific Production
deployment workflow.

## What it requires

The workflow is manual and requires:

- the exact approved commit SHA;
- explicit `DEPLOY` confirmation;
- a stable Production target identifier;
- a non-local HTTPS Production endpoint;
- an expected runtime deployment identifier;
- a successful immutable Release Approval artifact for the exact commit.

It resolves the Release Approval first, follows that evidence to the exact Stage
Admission and source CI run, downloads the exact release bundle, and re-verifies the
entire governance chain.

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
- backend/frontend image IDs;
- release approver;
- deployment operator;
- change reference;
- Production target and HTTPS endpoint;
- expected runtime deployment identifier.

The artifact deliberately records `production_deployed=false`.

## Important boundary

This is **not** proof of a Hosted Production deployment. It is the final admission
artifact a future provider-specific deployment must consume before changing Production.
The deployment workflow must later emit separate evidence that the admitted image IDs
were actually deployed and healthy at the approved endpoint.

## Governance chain

```text
CI
→ immutable release artifact
→ Stage Admission PASSED
→ explicit Human Release Approval
→ Production Deployment Admission
→ provider-specific Hosted Production deployment
→ Production verification
→ Monitoring
```
