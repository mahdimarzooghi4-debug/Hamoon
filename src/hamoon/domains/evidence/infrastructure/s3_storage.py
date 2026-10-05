from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from hamoon.domains.evidence.ports.repositories import StoredEvidenceObject


class S3CompatibleEvidenceStorage:
    """Minimal private S3-compatible storage adapter using AWS Signature V4."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(endpoint.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("EVIDENCE_S3_ENDPOINT_INVALID")
        if not access_key or not secret_key or not bucket or not region:
            raise ValueError("EVIDENCE_S3_CONFIGURATION_INVALID")
        self._scheme = parsed.scheme
        self._netloc = parsed.netloc
        self._endpoint_path = parsed.path.rstrip("/")
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket
        self._region = region
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @staticmethod
    def _digest(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _sign(key: bytes, value: str) -> bytes:
        return hmac.new(key, value.encode(), hashlib.sha256).digest()

    def _authorization(
        self,
        *,
        method: str,
        canonical_uri: str,
        payload_hash: str,
        headers: dict[str, str],
        now: datetime,
    ) -> str:
        canonical_header_names = sorted(name.lower() for name in headers)
        canonical_headers = "".join(
            f"{name}:{' '.join(headers[name].strip().split())}\n"
            for name in canonical_header_names
        )
        signed_headers = ";".join(canonical_header_names)
        canonical_request = (
            f"{method}\n{canonical_uri}\n\n{canonical_headers}\n"
            f"{signed_headers}\n{payload_hash}"
        )
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        credential_scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        string_to_sign = (
            "AWS4-HMAC-SHA256\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )
        date_key = self._sign(
            f"AWS4{self._secret_key}".encode(),
            date_stamp,
        )
        region_key = self._sign(date_key, self._region)
        service_key = self._sign(region_key, "s3")
        signing_key = self._sign(service_key, "aws4_request")
        signature = hmac.new(
            signing_key,
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()
        return (
            "AWS4-HMAC-SHA256 "
            f"Credential={self._access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

    def _target(self, storage_key: str) -> tuple[str, str]:
        raw_path = f"{self._endpoint_path}/{self._bucket}/{storage_key}"
        canonical_uri = quote(raw_path, safe="/-_.~")
        url = urlunsplit(
            (
                self._scheme,
                self._netloc,
                canonical_uri,
                "",
                "",
            )
        )
        return url, canonical_uri

    async def _request(
        self,
        *,
        method: str,
        storage_key: str,
        content: bytes = b"",
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        url, canonical_uri = self._target(storage_key)
        now = datetime.now(UTC)
        payload_hash = self._digest(content)
        headers = {
            "host": self._netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": now.strftime("%Y%m%dT%H%M%SZ"),
        }
        if extra_headers:
            headers.update(
                {name.lower(): value for name, value in extra_headers.items()}
            )
        headers["authorization"] = self._authorization(
            method=method,
            canonical_uri=canonical_uri,
            payload_hash=payload_hash,
            headers=headers,
            now=now,
        )
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                return await client.request(
                    method,
                    url,
                    headers=headers,
                    content=content,
                )
        except httpx.HTTPError as exc:
            raise ValueError("EVIDENCE_STORAGE_UNAVAILABLE") from exc

    async def put(
        self,
        *,
        storage_key: str,
        content: bytes,
    ) -> StoredEvidenceObject:
        digest = self._digest(content)
        response = await self._request(
            method="PUT",
            storage_key=storage_key,
            content=content,
            extra_headers={
                "if-none-match": "*",
                "x-amz-meta-sha256": digest,
            },
        )
        if response.status_code in {409, 412}:
            raise ValueError("EVIDENCE_OBJECT_ALREADY_EXISTS")
        if response.is_error:
            raise ValueError("EVIDENCE_STORAGE_UNAVAILABLE")
        return StoredEvidenceObject(
            size_bytes=len(content),
            sha256=digest,
        )

    async def metadata(
        self,
        *,
        storage_key: str,
    ) -> StoredEvidenceObject | None:
        response = await self._request(
            method="HEAD",
            storage_key=storage_key,
        )
        if response.status_code == 404:
            return None
        if response.is_error:
            raise ValueError("EVIDENCE_STORAGE_UNAVAILABLE")
        raw_size = response.headers.get("content-length")
        digest = response.headers.get("x-amz-meta-sha256")
        if raw_size is None or digest is None:
            raise ValueError("EVIDENCE_STORAGE_METADATA_INVALID")
        try:
            size_bytes = int(raw_size)
        except ValueError as exc:
            raise ValueError("EVIDENCE_STORAGE_METADATA_INVALID") from exc
        return StoredEvidenceObject(
            size_bytes=size_bytes,
            sha256=digest.lower(),
        )

    async def delete_verification_object(
        self,
        *,
        storage_key: str,
    ) -> None:
        parts = storage_key.split("/")
        if (
            len(parts) < 2
            or parts[0] != "_hamoon-verification"
            or any(part in {"", ".", ".."} for part in parts[1:])
        ):
            raise ValueError("EVIDENCE_VERIFICATION_DELETE_KEY_INVALID")
        response = await self._request(
            method="DELETE",
            storage_key=storage_key,
        )
        if response.status_code == 404:
            return
        if response.is_error:
            raise ValueError("EVIDENCE_STORAGE_UNAVAILABLE")

    async def read(
        self,
        *,
        storage_key: str,
    ) -> bytes:
        response = await self._request(
            method="GET",
            storage_key=storage_key,
        )
        if response.status_code == 404:
            raise LookupError("EVIDENCE_OBJECT_NOT_FOUND")
        if response.is_error:
            raise ValueError("EVIDENCE_STORAGE_UNAVAILABLE")
        return response.content
