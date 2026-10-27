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
   Stage Admission run. The workflow publishes the unchanged images, reports their
   immutable registry digests, and uploads `render-image-digests.json` as the
   `hamoon-render-image-digests-<commit SHA>` artifact. Use its exact backend and
   frontend image references when writing the Blueprint. GHCR read access for Render
   still needs configuration.
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


## Hosted Stage service map

| Component | Render model | Container behavior | Data / network |
| --- | --- | --- | --- |
| Web | Public web service, image-backed | Nginx listens on port 80; API proxy uses the API private host and port | OIDC issuer and browser client configuration |
| API | Private service, image-backed | Uvicorn listens on port 8000; readiness path is `/health/ready`; run `alembic upgrade head` as a pre-deploy command | Render Postgres, NATS, Temporal, OIDC/JWKS, private S3-compatible evidence and model-artifact buckets, HTTPS scanner, OTLP traces/logs |
| Outbox worker | Background worker, same API image | `python -m hamoon.infrastructure.events.outbox` | PostgreSQL and NATS |
| Temporal worker | Background worker, same API image | `python -m hamoon.infrastructure.temporal.worker` | PostgreSQL and Temporal |
| Provider worker | Background worker, same API image | `python -m hamoon.infrastructure.temporal.provider_worker` | PostgreSQL and Temporal |
| PostgreSQL | Managed Render Postgres | Application database only | Async URL normalization is included in PR #23 |
| NATS / Temporal | Existing managed endpoints or separately operated services | Not part of the Hamoon image | Valid TLS/auth settings and endpoint/namespace are required |
| OIDC, object storage, scanner, telemetry | Existing approved providers | External integration endpoints | HTTPS origins, credentials and buckets are environment-owned |

New Render service names should be unique and kept in the Frankfurt region if all
Render-hosted private-network peers are placed there. Render private networking only
connects services in the same workspace and region; a private API should receive the
web service's traffic on its internal address.

## Stage environment configuration

The final Blueprint must provide the following values by reference or via Render
environment settings; secrets never belong in Git:

- Shared by API and workers: `HAMOON_ENVIRONMENT=stage`,
  `HAMOON_DEPLOYMENT_ID`, the backend `HAMOON_IMAGE_ID`,
  `HAMOON_DATABASE_URL`, `HAMOON_NATS_URL`, and
  `HAMOON_TEMPORAL_ADDRESS`.
- API: `HAMOON_OIDC_ISSUER_URL`, `HAMOON_OIDC_JWKS_URL`,
  `HAMOON_OIDC_AUDIENCE`, evidence S3 endpoint/access key/secret/bucket,
  internal-model-artifact S3 endpoint/access key/secret/bucket, scanner backend,
  HTTPS scanner endpoint/token, OTLP trace and log endpoints/headers, and a
  metrics access token.
- Web: `HAMOON_API_PROXY_UPSTREAM`, `HAMOON_WEB_OIDC_ISSUER_URL`,
  `HAMOON_WEB_OIDC_CLIENT_ID`, frontend image ID and deployment ID.
- The identity provider must register the actual hosted-web origin and callback URI.
  NATS and Temporal connection/authentication modes must match the capabilities in
  the application clients before a hosted Stage can start.

The API image embeds its Git commit and application version. The promotion workflow
will expose both the registry manifest digests and the Docker image IDs; Render's
image URL must use the immutable registry digest, while `HAMOON_IMAGE_ID` must
match the image ID expected by the release health endpoint.

## Why the deployable Blueprint is still pending

A Render `image.url` is a concrete registry reference. PR #23 produces a
commit-specific GHCR tag only after a successful main CI run and matching Stage
Admission, and the registry manifest digest is available only after the manual
promotion workflow runs. The Blueprint must therefore be filled with those exact
digests after promotion; a guessed tag, branch build, or placeholder digest would
not be a deployable Stage configuration.

The connected Render workspace currently has no Hamoon service. No Render resource
or registry credential has been created by this preparation.
