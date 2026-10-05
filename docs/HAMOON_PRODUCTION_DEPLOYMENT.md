# Hamoon — Hosted Production Deployment Execution

Status: Provider-neutral execution contract implemented. A concrete Production
orchestrator endpoint and its credentials are still environment-owned external
dependencies.

## Position in the release chain

```text
CI
→ immutable release artifact
→ Stage Admission
→ explicit Human Release Approval
→ Production Deployment Admission
→ Production Deploy
→ Production Verification
→ Production Monitoring
```

Release Approval and Production Deployment Admission are authorization evidence.
Neither one means that Production has changed.

Only the `Production Deploy` workflow may emit immutable evidence with:

```text
status = DEPLOYED
production_deployed = true
```

and only after a trusted deployment orchestrator returns a final receipt bound to the
exact admitted release.

## Provider-neutral orchestrator contract

The workflow uses a Production GitHub Environment and reads two environment secrets:

```text
HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT
HAMOON_DEPLOY_ORCHESTRATOR_TOKEN
```

The endpoint must be remote HTTPS. Localhost and local endpoints are rejected. The
bearer token must not be stored in the repository, release artifact, request artifact
or deployment attestation.

The request contains only release/deployment identity and governance references:

- repository;
- exact commit SHA;
- source CI run;
- immutable release artifact name;
- Production target;
- approved Production HTTPS endpoint;
- expected deployment ID;
- backend image ID and archive SHA-256;
- frontend image ID and archive SHA-256;
- Release Approval and Deployment Admission references.

No Household data, PII, application secrets, provider credentials or AI credentials
are sent by this contract.

## Synchronous and asynchronous execution

The orchestrator may return `DEPLOYED` immediately, or:

```text
ACCEPTED / IN_PROGRESS
+ status_url
```

Hamoon then polls until the final state.

Security rule:

> The status URL must remain HTTPS on the exact same hostname as the configured
> orchestrator endpoint.

This prevents the deployment bearer token from following a cross-host status URL.

Redirects are not followed automatically.

## Final receipt

A successful final receipt must include:

```text
status = DEPLOYED
receipt_id
commit_sha
deployment_id
production_target
production_endpoint
backend_image_id
frontend_image_id
deployed_at
```

Every identity must exactly match the admitted request. Image drift, target drift,
endpoint drift or deployment-ID drift fails deployment execution.

`deployed_at` must contain timezone information.

## Immutable deployment evidence

The workflow stores:

```text
hamoon-production-deployment-<commit-sha>/
  orchestrator-request.json
  orchestrator-receipt.json
  production-deployment.json
```

The deployment attestation binds SHA-256 hashes of:

- release manifest;
- Production Deployment Admission;
- orchestrator request;
- orchestrator receipt.

It also records the human deployer and the GitHub Actions deployment run ID.

## Production Verification dependency

Production Verification now requires this deployment artifact. It re-verifies the
request/receipt/attestation chain before probing the hosted runtime.

Therefore this state is invalid:

```text
Production Deployment Admission exists
+ hosted endpoint happens to answer
+ no immutable Production deployment receipt
→ NOT VERIFIED
```

The valid state is:

```text
Admission
→ trusted orchestrator DEPLOYED receipt
→ immutable deployment attestation
→ hosted runtime identity probe
→ Production Verification VERIFIED
```

## External responsibilities

The concrete orchestrator is intentionally outside Hamoon's application code. It must
be able to:

1. authenticate the Hamoon deployment request;
2. fetch/import the immutable release artifact using its own authorized GitHub access;
3. deploy the exact backend/frontend image identities;
4. run the platform-specific migration/release procedure;
5. expose the approved HTTPS Production endpoint;
6. return a final receipt only when the platform has completed the deployment.

The orchestrator must not rebuild application images.

## GitHub Environment policy

The workflow targets:

```text
environment: production
```

Repository operators should configure that GitHub Environment with:

- required human reviewers;
- restricted deployment branches/tags as appropriate;
- the orchestrator endpoint secret;
- the orchestrator bearer token;
- environment-specific audit/rotation policy.

## Non-goals

This contract does not choose Render, Kubernetes, AWS, Azure, GCP or another specific
runtime. ADR-008 remains authoritative: Hamoon V1 is managed-container/PaaS oriented
and vendor-neutral.

A concrete platform adapter may be placed behind the orchestrator without changing the
Hamoon release governance chain.
