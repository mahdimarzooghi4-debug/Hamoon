from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal, cast

import httpx

from hamoon.domains.evidence.ports.repositories import EvidenceScanner


@dataclass(frozen=True, slots=True)
class EvidenceScanResponse:
    status: Literal["CLEAN", "INFECTED"]
    detail: str | None = None


class HttpEvidenceScanner(EvidenceScanner):
    def __init__(
        self,
        *,
        endpoint: str,
        bearer_token: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("EVIDENCE_SCANNER_ENDPOINT_INVALID")
        if len(bearer_token.strip()) < 16:
            raise ValueError("EVIDENCE_SCANNER_TOKEN_INVALID")
        if timeout_seconds <= 0:
            raise ValueError("EVIDENCE_SCANNER_TIMEOUT_INVALID")
        self._endpoint = endpoint
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def _scan(
        self,
        client: httpx.AsyncClient,
        *,
        media_type: str,
        content: bytes,
    ) -> httpx.Response:
        digest = hashlib.sha256(content).hexdigest()
        return await client.post(
            self._endpoint,
            content=content,
            headers={
                "Authorization": f"Bearer {self._bearer_token}",
                "Content-Type": media_type,
                "X-Content-SHA256": digest,
            },
        )

    async def scan(
        self,
        *,
        media_type: str,
        content: bytes,
    ) -> tuple[bool, str | None]:
        try:
            if self._client is not None:
                response = await self._scan(
                    self._client,
                    media_type=media_type,
                    content=content,
                )
            else:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                ) as client:
                    response = await self._scan(
                        client,
                        media_type=media_type,
                        content=content,
                    )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ValueError("EVIDENCE_SCANNER_UNAVAILABLE") from exc

        if response.status_code >= 500:
            raise ValueError("EVIDENCE_SCANNER_UNAVAILABLE")
        if response.status_code < 200 or response.status_code >= 300:
            raise ValueError("EVIDENCE_SCANNER_REJECTED")

        try:
            decoded = cast(object, response.json())
        except ValueError as exc:
            raise ValueError("EVIDENCE_SCANNER_RESPONSE_INVALID") from exc
        if not isinstance(decoded, dict):
            raise ValueError("EVIDENCE_SCANNER_RESPONSE_INVALID")
        payload = cast(dict[str, object], decoded)

        raw_status = payload.get("status")
        raw_detail = payload.get("detail")
        status_value: Literal["CLEAN", "INFECTED"]
        if raw_status == "CLEAN":
            status_value = "CLEAN"
        elif raw_status == "INFECTED":
            status_value = "INFECTED"
        else:
            raise ValueError("EVIDENCE_SCANNER_RESPONSE_INVALID")
        if raw_detail is not None and not isinstance(raw_detail, str):
            raise ValueError("EVIDENCE_SCANNER_RESPONSE_INVALID")

        result = EvidenceScanResponse(
            status=status_value,
            detail=raw_detail,
        )
        return result.status == "CLEAN", result.detail
