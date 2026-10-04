from __future__ import annotations

from hashlib import sha256

import httpx
import pytest

from hamoon.domains.evidence.infrastructure.s3_storage import (
    S3CompatibleEvidenceStorage,
)


@pytest.mark.asyncio
async def test_s3_storage_put_metadata_and_read_are_private_and_signed() -> None:
    content = b"private evidence"
    digest = sha256(content).hexdigest()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        authorization = request.headers.get("authorization", "")
        assert authorization.startswith("AWS4-HMAC-SHA256 ")
        assert "SignedHeaders=" in authorization
        if request.method == "PUT":
            assert request.headers["if-none-match"] == "*"
            assert request.headers["x-amz-meta-sha256"] == digest
            return httpx.Response(200)
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={
                    "content-length": str(len(content)),
                    "x-amz-meta-sha256": digest,
                },
            )
        if request.method == "GET":
            return httpx.Response(200, content=content)
        raise AssertionError(request.method)

    storage = S3CompatibleEvidenceStorage(
        endpoint="https://objects.example.internal",
        access_key="access",
        secret_key="secret",
        bucket="hamoon-evidence",
        transport=httpx.MockTransport(handler),
    )

    stored = await storage.put(
        storage_key="evidence/test/2026/10/object",
        content=content,
    )
    assert stored.size_bytes == len(content)
    assert stored.sha256 == digest

    metadata = await storage.metadata(
        storage_key="evidence/test/2026/10/object",
    )
    assert metadata is not None
    assert metadata.size_bytes == len(content)
    assert metadata.sha256 == digest

    assert (
        await storage.read(storage_key="evidence/test/2026/10/object")
        == content
    )
    assert [request.method for request in seen] == ["PUT", "HEAD", "GET"]
    assert all(
        request.url.path == "/hamoon-evidence/evidence/test/2026/10/object"
        for request in seen
    )


@pytest.mark.asyncio
async def test_s3_storage_rejects_overwrite() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(412)

    storage = S3CompatibleEvidenceStorage(
        endpoint="https://objects.example.internal",
        access_key="access",
        secret_key="secret",
        bucket="hamoon-evidence",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ValueError, match="EVIDENCE_OBJECT_ALREADY_EXISTS"):
        await storage.put(storage_key="evidence/object", content=b"immutable")
