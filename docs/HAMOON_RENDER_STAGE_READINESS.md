# Hamoon hosted Stage on Render

Status: **runtime compatibility preparation started; no Render service has been created**

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

1. Select a private image registry and configure Render read access without placing
   a registry token in Git.
2. Add the promotion step that publishes only the already-admitted OCI images,
   records each registry digest, and refuses to overwrite a release SHA.
3. Create the Render Blueprint using those immutable image digests and an isolated
   Stage database.
4. Provide the Stage NATS, Temporal, OIDC, S3, scanner, and telemetry endpoints and
   secrets through Render's environment configuration.
5. Run authenticated desktop/mobile browser review against the canonical Figma
   frames and record the remaining visual differences before calling the UI aligned.

The existing synthetic Chromium correction checks cover behavior and layout
constraints; they are not pixel-level Figma approval.
