from __future__ import annotations

import hashlib
import ipaddress
import re
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4

import httpx

from hamoon.domains.evidence.infrastructure.http_scanner import HttpEvidenceScanner
from hamoon.domains.evidence.infrastructure.s3_storage import (
    S3CompatibleEvidenceStorage,
)

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SYNTHETIC_CONTENT = b"HAMOON_EVIDENCE_INTEGRATION_VERIFICATION_V1\n"
_OVERWRITE_CONTENT = b"HAMOON_EVIDENCE_INTEGRATION_OVERWRITE_PROBE_V1\n"


class EvidenceIntegrationVerificationError(RuntimeError):
    """External Evidence storage/scanner verification failed safely."""


def _remote_https(value: str) -> bool:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or parsed.hostname is None:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_loopback
        or address.is_link_local
        or address.is_unspecified
    )


def _anonymous_bucket_list_url(
    *,
    endpoint: str,
    bucket: str,
) -> str:
    parsed = urlsplit(endpoint.rstrip("/"))
    raw_path = f"{parsed.path.rstrip('/')}/{bucket}"
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            quote(raw_path, safe="/-_.~"),
            "list-type=2&max-keys=1",
            "",
        )
    )


def _anonymous_object_url(
    *,
    endpoint: str,
    bucket: str,
    storage_key: str,
) -> str:
    parsed = urlsplit(endpoint.rstrip("/"))
    raw_path = f"{parsed.path.rstrip('/')}/{bucket}/{storage_key}"
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            quote(raw_path, safe="/-_.~"),
            "",
            "",
        )
    )


async def verify_evidence_integration(
    *,
    commit_sha: str,
    s3_endpoint: str,
    s3_access_key: str,
    s3_secret_key: str,
    s3_bucket: str,
    s3_region: str,
    scanner_endpoint: str,
    scanner_token: str,
    storage_timeout_seconds: float = 10.0,
    scanner_timeout_seconds: float = 20.0,
    storage_transport: httpx.AsyncBaseTransport | None = None,
    scanner_client: httpx.AsyncClient | None = None,
    anonymous_client: httpx.AsyncClient | None = None,
) -> dict[str, object]:
    if _COMMIT_RE.fullmatch(commit_sha) is None:
        raise EvidenceIntegrationVerificationError(
            "Evidence verification commit SHA is invalid."
        )
    if not _remote_https(s3_endpoint):
        raise EvidenceIntegrationVerificationError(
            "Evidence S3 verification endpoint must be remote HTTPS."
        )
    if not _remote_https(scanner_endpoint):
        raise EvidenceIntegrationVerificationError(
            "Evidence scanner verification endpoint must be remote HTTPS."
        )
    if not s3_access_key.strip() or len(s3_secret_key) < 16:
        raise EvidenceIntegrationVerificationError(
            "Evidence S3 verification credentials are invalid."
        )
    if not s3_bucket.strip() or not s3_region.strip():
        raise EvidenceIntegrationVerificationError(
            "Evidence S3 verification bucket/region is invalid."
        )
    if len(scanner_token.strip()) < 32:
        raise EvidenceIntegrationVerificationError(
            "Evidence scanner verification token is invalid."
        )

    verification_id = f"hamoon-evidence-verify-{uuid4()}"
    storage_key = (
        f"_hamoon-verification/{commit_sha}/{verification_id}.txt"
    )
    digest = hashlib.sha256(_SYNTHETIC_CONTENT).hexdigest()

    storage = S3CompatibleEvidenceStorage(
        endpoint=s3_endpoint,
        access_key=s3_access_key,
        secret_key=s3_secret_key,
        bucket=s3_bucket,
        region=s3_region,
        timeout_seconds=storage_timeout_seconds,
        transport=storage_transport,
    )
    scanner = HttpEvidenceScanner(
        endpoint=scanner_endpoint,
        bearer_token=scanner_token,
        timeout_seconds=scanner_timeout_seconds,
        client=scanner_client,
    )

    checks: dict[str, bool] = {
        "storage_put": False,
        "storage_overwrite_denied": False,
        "storage_metadata_integrity": False,
        "storage_signed_read_integrity": False,
        "storage_anonymous_read_denied": False,
        "storage_anonymous_list_denied": False,
        "scanner_clean": False,
        "storage_cleanup": False,
    }

    try:
        stored = await storage.put(
            storage_key=storage_key,
            content=_SYNTHETIC_CONTENT,
        )
        if stored.size_bytes != len(_SYNTHETIC_CONTENT) or stored.sha256 != digest:
            raise EvidenceIntegrationVerificationError(
                "Evidence S3 PUT identity mismatch."
            )
        checks["storage_put"] = True

        try:
            await storage.put(
                storage_key=storage_key,
                content=_OVERWRITE_CONTENT,
            )
        except ValueError as exc:
            if str(exc) != "EVIDENCE_OBJECT_ALREADY_EXISTS":
                raise
            checks["storage_overwrite_denied"] = True
        else:
            raise EvidenceIntegrationVerificationError(
                "Evidence S3 overwrite protection is not enforced."
            )

        metadata = await storage.metadata(storage_key=storage_key)
        if (
            metadata is None
            or metadata.size_bytes != len(_SYNTHETIC_CONTENT)
            or metadata.sha256 != digest
        ):
            raise EvidenceIntegrationVerificationError(
                "Evidence S3 metadata integrity verification failed."
            )
        checks["storage_metadata_integrity"] = True

        content = await storage.read(storage_key=storage_key)
        if content != _SYNTHETIC_CONTENT:
            raise EvidenceIntegrationVerificationError(
                "Evidence S3 signed read integrity verification failed."
            )
        checks["storage_signed_read_integrity"] = True

        anonymous_url = _anonymous_object_url(
            endpoint=s3_endpoint,
            bucket=s3_bucket,
            storage_key=storage_key,
        )
        owns_anonymous_client = anonymous_client is None
        client = anonymous_client or httpx.AsyncClient(
            timeout=storage_timeout_seconds,
            follow_redirects=False,
        )
        try:
            anonymous_response = await client.get(anonymous_url)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise EvidenceIntegrationVerificationError(
                "Anonymous Evidence S3 privacy probe failed."
            ) from exc
        finally:
            if owns_anonymous_client:
                await client.aclose()
        if anonymous_response.status_code not in {401, 403, 404}:
            raise EvidenceIntegrationVerificationError(
                "Evidence S3 object is not proven private."
            )
        checks["storage_anonymous_read_denied"] = True

        bucket_list_url = _anonymous_bucket_list_url(
            endpoint=s3_endpoint,
            bucket=s3_bucket,
        )
        owns_list_client = anonymous_client is None
        list_client = anonymous_client or httpx.AsyncClient(
            timeout=storage_timeout_seconds,
            follow_redirects=False,
        )
        try:
            list_response = await list_client.get(bucket_list_url)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise EvidenceIntegrationVerificationError(
                "Anonymous Evidence S3 bucket privacy probe failed."
            ) from exc
        finally:
            if owns_list_client:
                await list_client.aclose()
        if list_response.status_code not in {401, 403, 404}:
            raise EvidenceIntegrationVerificationError(
                "Evidence S3 bucket listing is not proven private."
            )
        checks["storage_anonymous_list_denied"] = True

        clean, _detail = await scanner.scan(
            media_type="text/plain",
            content=_SYNTHETIC_CONTENT,
        )
        if not clean:
            raise EvidenceIntegrationVerificationError(
                "Evidence scanner did not classify synthetic payload as CLEAN."
            )
        checks["scanner_clean"] = True
    except EvidenceIntegrationVerificationError:
        raise
    except (ValueError, LookupError) as exc:
        raise EvidenceIntegrationVerificationError(
            "Evidence integration verification failed."
        ) from exc
    finally:
        try:
            await storage.delete_verification_object(storage_key=storage_key)
            remaining = await storage.metadata(storage_key=storage_key)
            checks["storage_cleanup"] = remaining is None
        except (ValueError, LookupError):
            checks["storage_cleanup"] = False

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise EvidenceIntegrationVerificationError(
            "Evidence integration failed required checks: " + ",".join(failed)
        )

    return {
        "schema_version": 1,
        "status": "VERIFIED",
        "verification_scope": "EXTERNAL_EVIDENCE_STORAGE_SCANNER",
        "verification_id": verification_id,
        "commit_sha": commit_sha,
        "synthetic": True,
        "contains_pii": False,
        "object_sha256": digest,
        "object_size_bytes": len(_SYNTHETIC_CONTENT),
        "checks": checks,
        "verified_at": datetime.now(UTC).isoformat(),
    }
