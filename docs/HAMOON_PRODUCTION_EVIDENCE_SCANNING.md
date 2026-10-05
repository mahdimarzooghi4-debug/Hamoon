# Hamoon — Production Evidence Scanning

Status: production evidence scanning is fail-closed and provider-neutral. Repository/Stage tests prove the adapter contract, and a separate External Evidence Integration Verification gate can now prove the configured Production scanner and S3-compatible storage with a synthetic PII-free live probe.

## Runtime modes

Local and Stage may use the deterministic `LocalEvidenceScanner` for media-signature and executable-content checks.

Production must configure:

```text
HAMOON_EVIDENCE_SCANNER_BACKEND=http
HAMOON_EVIDENCE_SCANNER_ENDPOINT=https://<approved-scanner>/v1/scan
HAMOON_EVIDENCE_SCANNER_TOKEN=<secret-manager-injected bearer token>
HAMOON_EVIDENCE_SCANNER_TIMEOUT_SECONDS=<positive timeout>
```

Production startup validation rejects a local scanner, a non-HTTPS scanner endpoint, or a missing/short token.

## HTTP scanner contract

Hamoon sends one authenticated HTTPS POST with:

- the evidence bytes as the request body;
- the declared media type as `Content-Type`;
- `X-Content-SHA256` computed by Hamoon;
- a bearer token from runtime secret configuration.

Redirects are not followed, so credentials are never intentionally forwarded to another origin.

The scanner response is constrained to:

```json
{"status":"CLEAN","detail":"optional engine detail"}
```

or

```json
{"status":"INFECTED","detail":"optional detection detail"}
```

Transport errors, HTTP 5xx, non-2xx responses, malformed JSON, or unknown status values fail closed. None of those conditions can promote evidence to `AVAILABLE`.

## Trust boundary

A `CLEAN` response allows the existing evidence finalization logic to publish `EvidenceAvailable`. An `INFECTED` response produces quarantine semantics.

Repository and Stage tests alone do not establish that a specific external scanner or storage endpoint is operational. The External Evidence Integration Verification workflow supplies that deployment-specific proof for connectivity, credential acceptance, private-object access, integrity, CLEAN scanning and synthetic cleanup. Scanner engine/signature lifecycle and long-term storage retention remain separate operational evidence.
