# ADR-004 — Hamoon Evidence & Object Storage

> وضعیت: Accepted for V1  
> دامنه تصمیم: Evidence Binary Storage, Metadata, Access, Integrity, Upload/Download Flow, Retention  
> وابسته به:
> - `HAMOON_DATA_MODEL_V1.md`
> - `HAMOON_SECURITY_RBAC_V1.md`
> - `ADR-001-HAMOON-CORE-STACK.md`
> - `ADR-002-HAMOON-REPOSITORY-ENGINEERING-STANDARDS.md`
> - `ADR-003-HAMOON-IDENTITY-AUTHENTICATION.md`

---

# 1. Context

Hamoon باید بتواند Evidence مرتبط با پرونده خانوار، Factها، Assessmentها، Provider Resultها و تصمیم‌های انسانی/هوشمند را نگهداری کند.

نمونه Evidence:

- سند
- فایل PDF
- تصویر
- پاسخ سامانه بیرونی
- گزارش Provider
- یادداشت میدانی
- فایل پیوست‌شده به ارزیابی
- artifact مرتبط با تصمیم

این فایل‌ها نباید داخل PostgreSQL به‌صورت binary blob اصلی نگهداری شوند.

همچنین Evidence ممکن است حاوی داده حساس باشد و باید:

- private
- access-controlled
- auditable
- integrity-verifiable
- lifecycle-managed
- provider-isolated
- AI-minimized

باشد.

---

# 2. Decision Summary

برای V1:

```text
Evidence Metadata:
PostgreSQL

Binary/Object Storage Contract:
S3-compatible object storage

Local / Development Reference:
MinIO

Production Provider:
selected in Deployment ADR
but must satisfy S3-compatible storage interface
or equivalent adapter contract

Bucket Visibility:
Private only

Object Access:
short-lived signed access
after server-side authorization

Integrity:
SHA-256 content hash

Object Identity:
opaque storage key
not user filename

Versioning:
application-level evidence records
plus object versioning where supported

Malware / Content Validation:
upload pipeline hook required

AI Access:
through authorized evidence service,
not unrestricted direct bucket access
```

---

# 3. Why Object Storage

Evidence binaries have different requirements from relational data:

- large payloads
- streaming
- content-type handling
- lifecycle policies
- cheaper storage
- signed access
- object integrity
- archival

PostgreSQL remains the source of truth for:

- Evidence identity
- ownership
- classification
- authorization metadata
- object reference
- integrity hash
- audit linkage

Object storage stores binary content only.

---

# 4. Storage Abstraction

Hamoon domain/application code depends on:

```text
EvidenceStorage
```

not on AWS SDK, MinIO SDK or a specific cloud.

Logical interface:

```text
EvidenceStorage
- create_upload_target(...)
- finalize_upload(...)
- get_authorized_download_target(...)
- get_metadata(...)
- delete_by_policy(...)
- verify_integrity(...)
```

Vendor-specific implementation belongs in:

```text
infrastructure/storage/
```

---

# 5. Evidence Metadata

PostgreSQL entity:

```text
EVIDENCE
- id
- household_id
- evidence_type
- title
- description?
- storage_provider
- storage_bucket
- storage_key
- original_filename?
- media_type
- size_bytes
- sha256
- source_id?
- captured_at?
- recorded_at
- recorded_by
- sensitivity_class
- scan_status
- lifecycle_status
- schema_version
```

Binary content is never the authoritative value in this table.

---

# 6. Storage Key

Storage key must be opaque.

Recommended structure:

```text
evidence/<environment>/<organization>/<yyyy>/<mm>/<evidence_id>/<object_id>
```

Do not place:

- national ID
- household name
- phone
- human-readable sensitive case data

inside object keys.

---

# 7. Original Filename

Original filename may be retained only as metadata for user experience.

It must not be trusted for:

- path generation
- content type
- authorization
- executable behavior

Filename must be normalized/escaped when displayed.

---

# 8. Private Buckets Only

Public buckets are forbidden.

All evidence access follows:

```text
Authenticated Request
→ Authorization Check
→ Evidence Policy Check
→ short-lived signed URL / controlled stream
```

Permanent public URL is not allowed.

---

# 9. Upload Flow

Preferred V1 flow:

```text
Client
→ POST evidence metadata/init
→ Hamoon authorizes
→ Hamoon returns short-lived upload target
→ Client uploads object
→ Client/Storage callback finalize
→ Hamoon verifies object metadata/hash
→ scan pipeline
→ Evidence becomes AVAILABLE
```

For small files, API-streamed upload can be supported later, but direct authorized upload avoids unnecessary API bandwidth.

---

# 10. Upload Initialization API

Logical contract:

```text
POST /households/{id}/evidence/uploads
```

Request:

```json
{
  "evidence_type": "DOCUMENT",
  "title": "گزارش ارزیابی",
  "media_type": "application/pdf",
  "size_bytes": 245312,
  "sensitivity_class": "SENSITIVE_PERSONAL"
}
```

Response:

```json
{
  "data": {
    "evidence_id": "ev_...",
    "upload_url": "short-lived-signed-target",
    "expires_at": "...",
    "required_headers": {}
  }
}
```

---

# 11. Upload Finalization

Logical endpoint:

```text
POST /evidence/{id}/finalize
```

Server verifies:

- object exists
- expected size
- allowed media type
- hash
- ownership/scope
- upload session validity

Then scan status begins.

---

# 12. Evidence Lifecycle

```text
PENDING_UPLOAD
→ UPLOADED
→ SCANNING
→ AVAILABLE
```

Failure states:

```text
UPLOAD_FAILED
SCAN_FAILED
QUARANTINED
REJECTED
ARCHIVED
DELETED_BY_POLICY
```

No quarantined evidence is downloadable by normal users.

---

# 13. Integrity

Every stored object requires:

```text
SHA-256
```

Hash is stored in PostgreSQL.

Use cases:

- corruption detection
- duplicate diagnostics
- audit
- evidence integrity
- reproducibility

Hash equality alone must not automatically merge two evidence records.

---

# 14. Content Type Validation

Client-provided MIME type is untrusted.

Validation pipeline may inspect:

- declared content type
- object metadata
- file signature/magic bytes

Allowed content types are policy-driven.

Initial likely classes:

- PDF
- JPEG
- PNG
- selected office/document formats

Executable/script content is rejected unless explicitly approved by future policy.

---

# 15. File Size Policy

Maximum upload size must be configurable.

Limits may differ by:

- evidence type
- media type
- actor type
- integration/provider

Hard-coded UI-only size limits are insufficient; server/storage policy is authoritative.

---

# 16. Malware Scanning

Evidence pipeline must expose a malware/content scanning hook.

Flow:

```text
Uploaded
→ Quarantine/Scanning area
→ Scanner
→ Clean?
   Yes → AVAILABLE
   No  → QUARANTINED / REJECTED
```

Concrete scanning engine is deferred to deployment/security implementation.

---

# 17. Sensitivity Classification

Each Evidence has one of:

```text
INTERNAL
CONFIDENTIAL
SENSITIVE_PERSONAL
HIGHLY_SENSITIVE
```

PUBLIC is not expected for household evidence by default.

Classification affects:

- access
- download audit
- AI eligibility
- retention
- export
- provider sharing

---

# 18. Field/Resource Authorization

Evidence access requires:

```text
evidence.read
+ household/case scope
+ sensitivity permission
+ purpose
→ ALLOW / DENY
```

For some UI contexts:

```text
MASKED METADATA
```

may be returned without binary access.

---

# 19. Download Flow

```text
GET /evidence/{id}/download
```

Server:

1. authenticates actor
2. checks household/provider/resource scope
3. checks classification
4. records audit when required
5. returns short-lived signed URL or streams content

Signed URL should expire quickly.

---

# 20. Provider Evidence

Provider cannot upload arbitrary evidence to any household.

Flow:

```text
Provider Identity
→ own Referral
→ own Provider Result
→ Evidence upload authorization
```

Evidence is bound to:

- provider_id
- referral_id
- provider_result_id

before it can be attached to Hamoon domain records.

---

# 21. Provider Download

Provider can access only evidence explicitly included in its Referral Data Package.

Provider must never browse household evidence generally.

---

# 22. AI Evidence Access

AI Runtime has no unrestricted bucket credentials.

Preferred flow:

```text
AI Decision
→ Evidence Policy
→ authorized evidence reference/content extraction
→ Feature/Evidence Package
→ AI Runtime
```

The AI provider receives only evidence needed for the task.

---

# 23. AI and Binary Files

AI should not receive binary files by default.

Preferred order:

1. structured fact/metadata
2. approved extracted text/representation
3. only when required, binary/document input through approved provider path

Every AI-consumed evidence reference is recorded in Decision Trace.

---

# 24. Evidence Extraction

Text/document extraction is a separate derived artifact.

Logical entity:

```text
EVIDENCE_DERIVATIVE
- id
- evidence_id
- derivative_type
- storage_ref?
- text_ref?
- extractor_version
- created_at
- status
```

Examples:

```text
TEXT_EXTRACTION
THUMBNAIL
NORMALIZED_PDF
REDACTED_COPY
```

Original object remains immutable.

---

# 25. Immutability

Once Evidence reaches AVAILABLE:

> binary object must not be silently overwritten.

Replacement creates a new Evidence record/version and relation:

```text
old evidence
→ superseded_by
→ new evidence
```

---

# 26. Delete Semantics

Normal product delete must not physically destroy evidence immediately.

Logical states:

```text
AVAILABLE
→ ARCHIVED
→ DELETED_BY_POLICY
```

Physical deletion is governed by retention/legal/privacy policy.

---

# 27. Retention

Retention rules are policy-driven by:

- evidence type
- classification
- legal requirement
- case lifecycle
- provider contract

Concrete durations are deferred to Governance/Deployment decisions.

Architecture must support lifecycle rules per object/class.

---

# 28. Backup

Object storage must support backup/durability appropriate to production.

Requirements:

- encrypted
- restore-tested
- access-controlled
- environment-separated

Evidence metadata and binaries must be recoverable consistently.

---

# 29. Versioning

Object-store native versioning is recommended where supported.

However Hamoon does not rely on it as the sole evidence history.

Application-level Evidence records remain the business source of truth.

---

# 30. Encryption

Required:

- TLS in transit
- server-side encryption at rest
- encrypted backups

For HIGHLY_SENSITIVE evidence, stronger key separation may be introduced later.

---

# 31. Key Management

Production encryption keys are managed through deployment platform KMS/secret management.

Keys are never committed to repository.

---

# 32. MinIO Role

MinIO is the V1 reference for:

- local development
- automated integration tests
- stage when appropriate

It validates the S3-compatible adapter without locking production to a cloud vendor.

Production storage provider is decided in ADR-008 Deployment or environment-specific deployment record.

---

# 33. S3-Compatible Contract

The adapter should depend only on capabilities Hamoon actually needs:

- private object put/get
- metadata
- signed upload/download
- object existence
- lifecycle capability
- optional native versioning

Avoid dependence on vendor-only features unless documented in a later ADR.

---

# 34. Bucket Strategy

Reference logical buckets/containers:

```text
hamoon-evidence
hamoon-evidence-quarantine
hamoon-derived-artifacts
```

Environment separation:

```text
dev
stage
prod
```

must be physical or strongly isolated.

---

# 35. Quarantine

New uploads should not be exposed as AVAILABLE before scan/validation.

Quarantine storage may be separate bucket or isolated prefix with strict access policy.

---

# 36. Access URL Lifetime

Signed upload/download URLs must be short-lived and configurable.

They must not be persisted as durable business data.

Persist:

```text
storage_key
```

not the signed URL.

---

# 37. Audit

Audit mandatory for:

- evidence upload
- evidence finalization
- sensitive evidence view/download
- provider evidence access
- evidence sharing
- archive/delete by policy
- quarantine/release
- derivative generation when sensitive

---

# 38. Event Contracts

Core events:

```text
EvidenceUploadInitiated
EvidenceUploaded
EvidenceScanStarted
EvidenceAvailable
EvidenceQuarantined
EvidenceLinkedToFact
EvidenceLinkedToObservation
EvidenceLinkedToDecision
EvidenceArchived
EvidenceDeletedByPolicy
```

Payload carries IDs/metadata only, not binary content.

---

# 39. Database Tables / Collections

Minimum logical persistence:

```text
evidence
evidence_relations
evidence_derivatives
evidence_upload_sessions
evidence_access_audit
```

Existing domain relation tables may remain specific:

- fact_evidence
- indicator_observation_evidence
- provider_result_evidence
- human_decision_evidence

---

# 40. Evidence Relation

Generic relation may be used where beneficial:

```text
EVIDENCE_RELATION
- evidence_id
- resource_type
- resource_id
- relation_type
- created_at
- created_by
```

But core domain relations may remain explicit tables when integrity matters.

---

# 41. Duplicate Handling

Same SHA-256 may indicate identical bytes.

V1 rule:

- may flag potential duplicate
- do not automatically reuse across households
- do not leak existence across authorization boundaries
- do not deduplicate sensitive objects across tenants without explicit future design

---

# 42. Search / Index

Binary evidence is not searched directly.

Search indexes only authorized metadata and approved extracted text.

Search results must respect case/resource permissions.

---

# 43. Observability

Metrics:

```text
evidence_upload_started_total
evidence_upload_completed_total
evidence_upload_failed_total
evidence_scan_failed_total
evidence_quarantined_total
evidence_download_total
evidence_storage_error_total
evidence_bytes_stored
evidence_derivative_failed_total
```

No PII in metric labels.

---

# 44. Failure Handling

Examples:

```text
UPLOAD_SESSION_EXPIRED
OBJECT_NOT_FOUND
OBJECT_SIZE_MISMATCH
HASH_MISMATCH
MEDIA_TYPE_REJECTED
MALWARE_DETECTED
SCAN_UNAVAILABLE
STORAGE_UNAVAILABLE
EVIDENCE_ACCESS_DENIED
```

Errors must be structured and auditable.

---

# 45. Local Development

Local stack:

```text
FastAPI
PostgreSQL
NATS
MinIO
Keycloak
```

Integration tests can use isolated test bucket.

---

# 45.1 Production Integration Verification

A separate `External Evidence Integration Verification` gate may use a fixed synthetic
PII-free object under the reserved `_hamoon-verification/` prefix to prove the concrete
Production S3-compatible credentials, bucket privacy, integrity path and external scanner.

This verification cleanup capability is infrastructure-only and must not be exposed
through the normal `EvidenceStorage` domain protocol or used to delete real Evidence
objects.

The gate must prove anonymous access is denied and must remove the synthetic object even
when a later verification step fails.

# 46. Test Requirements

## Upload

- unauthorized upload denied
- wrong household scope denied
- expired upload session denied
- size mismatch rejected
- hash mismatch rejected
- invalid media type rejected

## Access

- unassigned caseworker denied
- manager masking policy respected
- provider cross-referral access denied
- signed URL expires
- quarantined object inaccessible

## Integrity

- stored hash matches object
- replacement creates new evidence record
- original available evidence is not overwritten

## AI

- AI cannot browse bucket
- AI accesses only approved evidence package
- Decision Trace records used evidence refs

---

# 47. Security Guardrails

1. No public bucket.
2. No permanent public URL.
3. No PII in storage key.
4. No client filename as trusted path.
5. No unrestricted AI storage credentials.
6. No provider bucket browsing.
7. No overwrite of AVAILABLE evidence.
8. No binary payload inside domain event.
9. No download without server authorization.
10. No production evidence copied to dev by default.

---

# 48. Consequences

## Positive

- scalable binary storage
- clean separation from relational database
- cloud portability
- private access model
- evidence integrity
- AI minimization
- provider isolation
- lifecycle readiness

## Trade-offs

- object storage is another infrastructure component
- upload finalization/scan workflow adds complexity
- metadata/object consistency must be monitored
- lifecycle policy needs operational governance

---

# 49. Acceptance Criteria

ADR-004 is implemented when:

- EvidenceStorage interface exists.
- MinIO adapter exists for local/test.
- metadata persists in PostgreSQL.
- private signed upload works.
- finalize/verify flow works.
- SHA-256 stored and validated.
- quarantine/scan state exists.
- authorized short-lived download works.
- provider evidence scope is enforced.
- AI has no unrestricted object storage credential.
- audit events are emitted.
- integration/security tests pass.

---

# 50. Next ADR

> **ADR-005 — Workflow Orchestration**

بعد از آن:

```text
ADR-006 — AI Provider Strategy
ADR-007 — Observability
ADR-008 — Deployment

→ Product Backlog
→ Sprint 1
```
