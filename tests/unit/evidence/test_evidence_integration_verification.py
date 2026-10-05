from __future__ import annotations

import hashlib

import httpx
import pytest

from hamoon.infrastructure.evidence_verification import (
    EvidenceIntegrationVerificationError,
    verify_evidence_integration,
)

COMMIT = "a" * 40
CONTENT = b"HAMOON_EVIDENCE_INTEGRATION_VERIFICATION_V1\n"
DIGEST = hashlib.sha256(CONTENT).hexdigest()


def _storage_transport(
    methods: list[str],
) -> httpx.MockTransport:
    state = {"exists": False}

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        assert request.url.path.startswith(
            "/hamoon-evidence/_hamoon-verification/"
        )
        authorization = request.headers.get("authorization", "")
        assert authorization.startswith("AWS4-HMAC-SHA256 ")

        if request.method == "PUT":
            assert request.headers["if-none-match"] == "*"
            if state["exists"]:
                return httpx.Response(412, request=request)
            assert request.headers["x-amz-meta-sha256"] == DIGEST
            state["exists"] = True
            return httpx.Response(200, request=request)

        if request.method == "HEAD":
            if not state["exists"]:
                return httpx.Response(404, request=request)
            return httpx.Response(
                200,
                headers={
                    "content-length": str(len(CONTENT)),
                    "x-amz-meta-sha256": DIGEST,
                },
                request=request,
            )

        if request.method == "GET":
            if not state["exists"]:
                return httpx.Response(404, request=request)
            return httpx.Response(200, content=CONTENT, request=request)

        if request.method == "DELETE":
            state["exists"] = False
            return httpx.Response(204, request=request)

        raise AssertionError(request.method)

    return httpx.MockTransport(handler)

@pytest.mark.asyncio
async def test_evidence_integration_verifies_private_storage_scanner_and_cleanup() -> None:
    storage_methods: list[str] = []

    def scanner_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer " + ("s" * 32)
        assert request.headers["content-type"] == "text/plain"
        assert request.headers["x-content-sha256"] == DIGEST
        assert request.content == CONTENT
        return httpx.Response(
            200,
            json={"status": "CLEAN", "detail": "engine-v1"},
            request=request,
        )

    def anonymous_handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(403, request=request)

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(scanner_handler),
            follow_redirects=False,
        ) as scanner_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(anonymous_handler),
            follow_redirects=False,
        ) as anonymous_client,
    ):
        observation = await verify_evidence_integration(
            commit_sha=COMMIT,
            s3_endpoint="https://objects.example.com",
            s3_access_key="access-key",
            s3_secret_key="secret-secret-secret-secret",
            s3_bucket="hamoon-evidence",
            s3_region="us-east-1",
            scanner_endpoint="https://scanner.example.com/v1/scan",
            scanner_token="s" * 32,
            storage_transport=_storage_transport(storage_methods),
            scanner_client=scanner_client,
            anonymous_client=anonymous_client,
        )

    assert observation["status"] == "VERIFIED"
    assert observation["synthetic"] is True
    assert observation["contains_pii"] is False
    assert observation["object_sha256"] == DIGEST
    assert observation["object_size_bytes"] == len(CONTENT)
    checks = observation["checks"]
    assert isinstance(checks, dict)
    assert all(checks.values())
    assert storage_methods == ["PUT", "PUT", "HEAD", "GET", "DELETE", "HEAD"]

@pytest.mark.asyncio
async def test_evidence_integration_rejects_public_object_and_still_cleans_up() -> None:
    storage_methods: list[str] = []

    def scanner_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "CLEAN"},
            request=request,
        )

    def anonymous_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=CONTENT, request=request)

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(scanner_handler),
            follow_redirects=False,
        ) as scanner_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(anonymous_handler),
            follow_redirects=False,
        ) as anonymous_client,
    ):
        with pytest.raises(
            EvidenceIntegrationVerificationError,
            match="not proven private",
        ):
            await verify_evidence_integration(
                commit_sha=COMMIT,
                s3_endpoint="https://objects.example.com",
                s3_access_key="access-key",
                s3_secret_key="secret-secret-secret-secret",
                s3_bucket="hamoon-evidence",
                s3_region="us-east-1",
                scanner_endpoint="https://scanner.example.com/v1/scan",
                scanner_token="s" * 32,
                storage_transport=_storage_transport(storage_methods),
                scanner_client=scanner_client,
                anonymous_client=anonymous_client,
            )

    assert "DELETE" in storage_methods
    assert storage_methods[-1] == "HEAD"

@pytest.mark.asyncio
async def test_evidence_integration_rejects_infected_scanner_result() -> None:
    storage_methods: list[str] = []

    def scanner_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "INFECTED", "detail": "test-signature"},
            request=request,
        )

    def anonymous_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(scanner_handler),
            follow_redirects=False,
        ) as scanner_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(anonymous_handler),
            follow_redirects=False,
        ) as anonymous_client,
    ):
        with pytest.raises(
            EvidenceIntegrationVerificationError,
            match="did not classify synthetic payload as CLEAN",
        ):
            await verify_evidence_integration(
                commit_sha=COMMIT,
                s3_endpoint="https://objects.example.com",
                s3_access_key="access-key",
                s3_secret_key="secret-secret-secret-secret",
                s3_bucket="hamoon-evidence",
                s3_region="us-east-1",
                scanner_endpoint="https://scanner.example.com/v1/scan",
                scanner_token="s" * 32,
                storage_transport=_storage_transport(storage_methods),
                scanner_client=scanner_client,
                anonymous_client=anonymous_client,
            )

    assert "DELETE" in storage_methods

@pytest.mark.asyncio
async def test_evidence_integration_rejects_non_https_external_endpoints() -> None:
    with pytest.raises(
        EvidenceIntegrationVerificationError,
        match="S3 verification endpoint must be remote HTTPS",
    ):
        await verify_evidence_integration(
            commit_sha=COMMIT,
            s3_endpoint="http://localhost:9000",
            s3_access_key="access-key",
            s3_secret_key="secret-secret-secret-secret",
            s3_bucket="hamoon-evidence",
            s3_region="us-east-1",
            scanner_endpoint="https://scanner.example.com/v1/scan",
            scanner_token="s" * 32,
        )


@pytest.mark.asyncio
async def test_evidence_integration_rejects_public_bucket_listing() -> None:
    storage_methods: list[str] = []
    anonymous_calls = 0

    def scanner_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "CLEAN"},
            request=request,
        )

    def anonymous_handler(request: httpx.Request) -> httpx.Response:
        nonlocal anonymous_calls
        anonymous_calls += 1
        if anonymous_calls == 1:
            return httpx.Response(403, request=request)
        return httpx.Response(200, content=b"<ListBucketResult/>", request=request)

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(scanner_handler),
            follow_redirects=False,
        ) as scanner_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(anonymous_handler),
            follow_redirects=False,
        ) as anonymous_client,
    ):
        with pytest.raises(
            EvidenceIntegrationVerificationError,
            match="bucket listing is not proven private",
        ):
            await verify_evidence_integration(
                commit_sha=COMMIT,
                s3_endpoint="https://objects.example.com",
                s3_access_key="access-key",
                s3_secret_key="secret-secret-secret-secret",
                s3_bucket="hamoon-evidence",
                s3_region="us-east-1",
                scanner_endpoint="https://scanner.example.com/v1/scan",
                scanner_token="s" * 32,
                storage_transport=_storage_transport(storage_methods),
                scanner_client=scanner_client,
                anonymous_client=anonymous_client,
            )

    assert "DELETE" in storage_methods
