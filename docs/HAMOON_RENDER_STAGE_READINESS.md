# Hamoon hosted Stage on Render

Status: **runtime compatibility and gated GHCR promotion are prepared in PR #23; no Render service or image publication has been created**

## Release boundary

Hamoon's hosted Stage must consume the exact backend and frontend OCI images from a
release bundle that has passed the separate Stage Admission workflow. Render Git
services that build from a branch are not the hosted-Stage path: they rebuild code
and would bypass the repository's build-once, Stage-Admission chain.

The intended sequence is:

```text
main commit
→ CI build, scan, and immutable release bundle
→ Stage Admission attestation
→ publish the same OCI images to a registry accessible to Render
→ Render deploys those image digests into an isolated hosted-Stage environment
→ authenticated browser review against canonical Figma
```

Do not connect a Render service to production data or treat a successful local
Stage Admission run as a hosted Stage deployment.

## Render runtime shape

The hosted Stage topology will need separate runtime processes:

- public web frontend, with API requests reverse-proxied over Render's private network;
- private FastAPI API;
- outbox, Temporal, and provider background workers;
- an isolated managed PostgreSQL database;
- NATS JetStream and Temporal endpoints;
- HTTPS OIDC issuer and browser client callback/origin configuration;
- private S3-compatible evidence storage and an HTTPS scanning endpoint.

The exact Render Blueprint and service sizes depend on the image registry, workspace
plan, and approved Stage integration endpoints. Secret values stay in Render's
environment settings and are never committed to this repository.

## Compatibility changes

- SQLAlchemy async persistence now accepts Render's standard `postgresql://` or
  `postgres://` connection string and normalizes it to `postgresql+asyncpg://`.
- The web container now accepts `HAMOON_API_PROXY_UPSTREAM=host:port`; local
  Docker Compose keeps its `api:8000` default, while a hosted service can use the
  private service address exposed by Render.
- The frontend's OIDC issuer remains runtime-configurable. The corresponding
  issuer/client redirect URI must be registered with the chosen OIDC provider.

## Remaining hosted-Stage setup

1. Review and merge the PR that adds a manual, attestation-gated GHCR publisher;
   after merge, use it only for a successful main CI run with a matching successful
   Stage Admission run. The workflow publishes the unchanged images and reports their
   immutable registry digests. GHCR read access for Render still needs configuration.
2. Create the Render Blueprint using those immutable image digests and an isolated
   Stage database.
3. Provide the Stage NATS, Temporal, OIDC, S3, scanner, and telemetry endpoints and
   secrets through Render's environment configuration.
4. Run authenticated desktop/mobile browser review against the canonical Figma
   frames and record the remaining visual differences before calling the UI aligned.

The existing synthetic Chromium correction checks cover behavior and layout
constraints; they are not pixel-level Figma approval.

## Figma/code parity status

The current reconciliation record remains open. The Home dashboard hierarchy was updated in PR #23 to the canonical search, journey,
summary, task-strip and household-table structure, using live API data. Header/navigation and brand asset parity and desktop/mobile screenshot comparison
remain open. The dashboard now shows an explicit forbidden state for 403 responses. Work queue and household detail views still need visual parity
review. The correction sheet has a route-addressable overlay and persisted workflow,
but its browser capture is not a pixel-level match to the canonical frame. The hosted
Stage browser review must include these routes before the UI is called aligned; Render
readiness does not imply design approval.
