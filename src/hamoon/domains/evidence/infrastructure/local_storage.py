from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from hamoon.domains.evidence.ports.repositories import StoredEvidenceObject


class LocalEvidenceStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, storage_key: str) -> Path:
        candidate = (self._root / storage_key).resolve()
        if self._root not in candidate.parents:
            raise ValueError("EVIDENCE_STORAGE_KEY_INVALID")
        return candidate

    async def put(
        self,
        *,
        storage_key: str,
        content: bytes,
    ) -> StoredEvidenceObject:
        path = self._path(storage_key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise ValueError("EVIDENCE_OBJECT_ALREADY_EXISTS")
            temporary = path.with_name(f".{path.name}.upload")
            temporary.write_bytes(content)
            os.replace(temporary, path)

        await asyncio.to_thread(_write)
        return StoredEvidenceObject(
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    async def metadata(
        self,
        *,
        storage_key: str,
    ) -> StoredEvidenceObject | None:
        path = self._path(storage_key)
        if not path.exists():
            return None
        content = await asyncio.to_thread(path.read_bytes)
        return StoredEvidenceObject(
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    async def read(
        self,
        *,
        storage_key: str,
    ) -> bytes:
        path = self._path(storage_key)
        if not path.exists():
            raise LookupError("EVIDENCE_OBJECT_NOT_FOUND")
        return await asyncio.to_thread(path.read_bytes)


class LocalEvidenceScanner:
    async def scan(
        self,
        *,
        media_type: str,
        content: bytes,
    ) -> tuple[bool, str | None]:
        if content.startswith(b"MZ") or content.startswith(b"\x7fELF"):
            return False, "EXECUTABLE_CONTENT_REJECTED"
        expected_magic: dict[str, tuple[bytes, ...]] = {
            "application/pdf": (b"%PDF-",),
            "image/jpeg": (b"\xff\xd8\xff",),
            "image/png": (b"\x89PNG\r\n\x1a\n",),
        }
        signatures = expected_magic.get(media_type)
        if signatures is not None and not content.startswith(signatures):
            return False, "MEDIA_SIGNATURE_MISMATCH"
        if media_type == "text/plain" and b"\x00" in content:
            return False, "TEXT_CONTENT_INVALID"
        return True, None


@dataclass(frozen=True, slots=True)
class EvidenceCapability:
    evidence_id: UUID
    purpose: str
    expires_at: datetime


class EvidenceCapabilitySigner:
    def __init__(self, secret: str) -> None:
        if len(secret) < 16:
            raise ValueError("EVIDENCE_SIGNING_SECRET_TOO_SHORT")
        self._secret = secret.encode("utf-8")

    def issue(
        self,
        *,
        evidence_id: UUID,
        purpose: str,
        ttl_seconds: int,
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        payload = {
            "evidence_id": str(evidence_id),
            "purpose": purpose,
            "expires_at": int(expires_at.timestamp()),
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).rstrip(b"=")
        signature = hmac.new(
            self._secret,
            encoded,
            hashlib.sha256,
        ).digest()
        token = (
            encoded.decode("ascii")
            + "."
            + base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
        )
        return token, expires_at

    def verify(
        self,
        *,
        token: str,
        purpose: str,
    ) -> EvidenceCapability:
        try:
            encoded_text, signature_text = token.split(".", 1)
            encoded = encoded_text.encode("ascii")
            signature = base64.urlsafe_b64decode(
                signature_text + "=" * (-len(signature_text) % 4)
            )
            expected = hmac.new(self._secret, encoded, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("EVIDENCE_CAPABILITY_INVALID")
            raw = base64.urlsafe_b64decode(
                encoded_text + "=" * (-len(encoded_text) % 4)
            )
            payload = json.loads(raw)
            evidence_id = UUID(str(payload["evidence_id"]))
            actual_purpose = str(payload["purpose"])
            expires_at = datetime.fromtimestamp(
                int(payload["expires_at"]),
                tz=UTC,
            )
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("EVIDENCE_CAPABILITY_INVALID") from exc

        if actual_purpose != purpose:
            raise ValueError("EVIDENCE_CAPABILITY_PURPOSE_MISMATCH")
        if expires_at <= datetime.now(UTC):
            raise ValueError("EVIDENCE_CAPABILITY_EXPIRED")
        return EvidenceCapability(
            evidence_id=evidence_id,
            purpose=actual_purpose,
            expires_at=expires_at,
        )
