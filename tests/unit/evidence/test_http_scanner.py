from __future__ import annotations

import hashlib

import httpx
import pytest

from hamoon.domains.evidence.infrastructure.http_scanner import HttpEvidenceScanner


@pytest.mark.asyncio
async def test_http_scanner_sends_digest_and_bearer_token() -> None:
    content = b"%PDF-1.7\nclean evidence\n"
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["authorization"] == "Bearer " + ("s" * 32)
        assert request.headers["content-type"] == "application/pdf"
        assert request.headers["x-content-sha256"] == hashlib.sha256(
            content
        ).hexdigest()
        return httpx.Response(
            200,
            json={"status": "CLEAN", "detail": "engine-v1"},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as client:
        scanner = HttpEvidenceScanner(
            endpoint="https://scanner.example.com/v1/scan",
            bearer_token="s" * 32,
            timeout_seconds=5,
            client=client,
        )
        clean, detail = await scanner.scan(
            media_type="application/pdf",
            content=content,
        )

    assert clean is True
    assert detail == "engine-v1"
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_http_scanner_reports_infected_without_exposing_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "INFECTED", "detail": "malware-signature"},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        scanner = HttpEvidenceScanner(
            endpoint="https://scanner.example.com/v1/scan",
            bearer_token="s" * 32,
            timeout_seconds=5,
            client=client,
        )
        clean, detail = await scanner.scan(
            media_type="application/pdf",
            content=b"%PDF-test",
        )

    assert clean is False
    assert detail == "malware-signature"


@pytest.mark.asyncio
async def test_http_scanner_fails_closed_on_service_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        scanner = HttpEvidenceScanner(
            endpoint="https://scanner.example.com/v1/scan",
            bearer_token="s" * 32,
            timeout_seconds=5,
            client=client,
        )
        with pytest.raises(ValueError, match="EVIDENCE_SCANNER_UNAVAILABLE"):
            await scanner.scan(
                media_type="image/png",
                content=b"\x89PNG\r\n\x1a\n",
            )


@pytest.mark.asyncio
async def test_http_scanner_rejects_invalid_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "UNKNOWN"},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        scanner = HttpEvidenceScanner(
            endpoint="https://scanner.example.com/v1/scan",
            bearer_token="s" * 32,
            timeout_seconds=5,
            client=client,
        )
        with pytest.raises(ValueError, match="EVIDENCE_SCANNER_RESPONSE_INVALID"):
            await scanner.scan(
                media_type="text/plain",
                content=b"hello",
            )
