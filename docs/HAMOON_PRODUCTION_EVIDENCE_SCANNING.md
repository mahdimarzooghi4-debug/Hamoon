# Hamoon — Production Evidence Scanning

Status: production evidence scanning is fail-closed and provider-neutral. Repository tests prove the adapter and configuration contract; they do not claim that a real Production scanner endpoint has processed evidence.

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

Repository and Stage tests do not establish that a specific external scanner vendor, engine version, signature database, retention policy, or Production endpoint is operational. Those remain deployment-specific evidence.
