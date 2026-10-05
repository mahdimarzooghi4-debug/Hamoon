# Hamoon — External Evidence Integration Verification

Status: executable Production verification gate implemented. Concrete S3-compatible
storage and scanner endpoints/credentials remain environment-owned dependencies.

## Purpose

Hamoon's Evidence runtime already enforces private S3-compatible storage, SHA-256
integrity, quarantine semantics and fail-closed malware scanning. Repository and Stage
tests prove those application contracts but cannot prove that the actual Production
storage credentials, bucket privacy or external scanner are operational.

The `External Evidence Integration Verification` workflow closes that gap without
creating a Household Evidence record or persisting business data.

## Verification scope

The gate validates, against the exact Stage-admitted commit:

```text
Production S3-compatible credentials
→ synthetic object PUT
→ metadata integrity
→ signed GET integrity
→ anonymous GET denied
→ external HTTPS scanner returns CLEAN
→ scoped synthetic object DELETE
→ object absence confirmed
```

The verification payload is a fixed PII-free text marker. No Household, Evidence,
Referral, user, contact or business payload is used.

## Synthetic storage key

The verifier creates an opaque key under the reserved prefix:

```text
_hamoon-verification/<commit-sha>/<verification-id>.txt
```

This prefix is reserved for verification only.

The normal `EvidenceStorage` domain protocol does not expose deletion. The S3 adapter
contains a dedicated cleanup method that refuses to delete any key outside
`_hamoon-verification/`. This prevents the verification workflow from becoming a
general Evidence deletion path.

## Required storage checks

Every run must prove:

- `storage_put`
- `storage_metadata_integrity`
- `storage_signed_read_integrity`
- `storage_anonymous_read_denied`
- `storage_cleanup`

The anonymous privacy check must receive HTTP 401 or 403 for the exact synthetic object.
A public 2xx response fails the gate.

Cleanup runs in a `finally` path so a scanner/privacy failure still attempts to remove
the synthetic object. Verification does not pass unless a final metadata lookup proves
the object is absent.

## Scanner check

The same fixed synthetic payload is sent to the configured HTTPS scanner using the
normal `HttpEvidenceScanner` contract. The scanner must return:

```text
status = CLEAN
```

Any transport error, authentication rejection, malformed response, `INFECTED` result
or unknown status fails the gate.

Scanner detail text is deliberately not persisted in the verification observation.

## Secrets and endpoints

The protected GitHub `production` Environment supplies:

```text
HAMOON_EVIDENCE_S3_ENDPOINT
HAMOON_EVIDENCE_S3_ACCESS_KEY
HAMOON_EVIDENCE_S3_SECRET_KEY
HAMOON_EVIDENCE_S3_BUCKET
HAMOON_EVIDENCE_S3_REGION
HAMOON_EVIDENCE_SCANNER_ENDPOINT
HAMOON_EVIDENCE_SCANNER_TOKEN
```

The workflow never writes endpoints, bucket names, access keys, secret keys, bearer
tokens or Authorization headers into its artifacts.

S3 and scanner verification endpoints must use remote HTTPS. Localhost, loopback,
link-local and unspecified IP endpoints are rejected.

## Governance binding

The manual workflow requires:

- exact 40-character commit SHA;
- explicit `VERIFY_EVIDENCE` confirmation;
- successful Stage Admission for the same commit;
- protected GitHub `production` Environment.

The immutable artifact is:

```text
hamoon-evidence-integration-<commit-sha>
```

and contains only:

```text
evidence-integration-observation.json
evidence-integration-verification.json
```

The attestation hashes the exact Stage attestation and sanitized observation and records
the human verifier and workflow run ID.

## Evidence safety

The offline verifier rejects observation keys such as:

```text
authorization
bearer_token
token
secret
secret_key
access_key
endpoint
bucket
storage_key
household_id
evidence_id
referral_id
national_id
phone
```

The observation retains only synthetic verification identity, object SHA-256/size,
boolean checks and timestamps.

## Relationship to Production preflight

Production runtime preflight already requires:

```text
evidence_s3_private_https = true
evidence_scanner_https = true
```

Those checks prove the deployment target's configuration contract. This external gate is
stronger: it performs live authenticated storage I/O, proves anonymous access denial,
executes the real scanner and cleans up the synthetic object.

A successful gate is infrastructure evidence only. It does not create or authorize a
real Evidence record and does not alter retention, legal hold or Evidence lifecycle
semantics.
