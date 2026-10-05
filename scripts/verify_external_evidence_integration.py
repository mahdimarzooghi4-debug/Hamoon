#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SYNTHETIC_CONTENT = b"HAMOON_EVIDENCE_INTEGRATION_VERIFICATION_V1\n"
SYNTHETIC_SHA256 = hashlib.sha256(SYNTHETIC_CONTENT).hexdigest()
FORBIDDEN_KEYS = {
    "authorization",
    "bearer_token",
    "token",
    "secret",
    "secret_key",
    "access_key",
    "endpoint",
    "bucket",
    "storage_key",
    "household_id",
    "evidence_id",
    "referral_id",
    "national_id",
    "phone",
}
REQUIRED_CHECKS = {
    "storage_put",
    "storage_metadata_integrity",
    "storage_signed_read_integrity",
    "storage_anonymous_read_denied",
    "scanner_clean",
    "storage_cleanup",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"evidence integration verification invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"evidence integration verification invalid: cannot parse {path}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recursive_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key).lower())
            keys.update(recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(recursive_keys(item))
    return keys


def parse_timestamp(value: object, field: str) -> datetime:
    require(isinstance(value, str), f"{field} missing")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(
            f"evidence integration verification invalid: {field} invalid"
        ) from exc
    require(parsed.tzinfo is not None, f"{field} must include timezone")
    return parsed


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: verify_external_evidence_integration.py "
            "<stage-attestation.json> <observation.json> <attestation.json>"
        )

    stage_path = Path(sys.argv[1])
    observation_path = Path(sys.argv[2])
    attestation_path = Path(sys.argv[3])

    stage = load_json(stage_path)
    observation = load_json(observation_path)
    attestation = load_json(attestation_path)

    require(stage.get("status") == "PASSED", "Stage Admission is not PASSED")
    commit_sha = stage.get("commit_sha")
    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "Stage commit_sha invalid",
    )
    stage_run_id = stage.get("stage_admission_run_id")
    require(
        isinstance(stage_run_id, str) and stage_run_id.isdigit(),
        "stage_admission_run_id invalid",
    )

    require(observation.get("schema_version") == 1, "observation schema unsupported")
    require(observation.get("status") == "VERIFIED", "observation status invalid")
    require(
        observation.get("verification_scope")
        == "EXTERNAL_EVIDENCE_STORAGE_SCANNER",
        "observation scope invalid",
    )
    require(observation.get("commit_sha") == commit_sha, "observation commit mismatch")
    require(observation.get("synthetic") is True, "observation must be synthetic")
    require(observation.get("contains_pii") is False, "observation must declare no PII")

    verification_id = observation.get("verification_id")
    require(
        isinstance(verification_id, str)
        and verification_id.startswith("hamoon-evidence-verify-"),
        "verification_id invalid",
    )
    object_sha256 = observation.get("object_sha256")
    require(
        isinstance(object_sha256, str)
        and SHA256_RE.fullmatch(object_sha256) is not None,
        "object_sha256 invalid",
    )
    require(
        object_sha256 == SYNTHETIC_SHA256,
        "object_sha256 does not match fixed synthetic payload",
    )
    object_size = observation.get("object_size_bytes")
    require(
        isinstance(object_size, int) and object_size == len(SYNTHETIC_CONTENT),
        "object_size_bytes does not match fixed synthetic payload",
    )
    checks = observation.get("checks")
    require(isinstance(checks, dict), "checks missing")
    require(set(checks) == REQUIRED_CHECKS, "check set invalid")
    for check in REQUIRED_CHECKS:
        require(checks.get(check) is True, f"required check failed: {check}")
    observed_at = parse_timestamp(observation.get("verified_at"), "observation verified_at")

    leaked = FORBIDDEN_KEYS & (
        recursive_keys(observation) | recursive_keys(attestation)
    )
    require(not leaked, f"forbidden evidence fields present {sorted(leaked)}")

    require(attestation.get("schema_version") == 1, "attestation schema unsupported")
    require(attestation.get("status") == "VERIFIED", "attestation status invalid")
    require(
        attestation.get("verification_scope")
        == "EXTERNAL_EVIDENCE_STORAGE_SCANNER",
        "attestation scope invalid",
    )
    require(
        attestation.get("external_evidence_integration_verified") is True,
        "external evidence integration not verified",
    )
    require(attestation.get("commit_sha") == commit_sha, "attestation commit mismatch")
    require(
        attestation.get("verification_id") == verification_id,
        "attestation verification_id mismatch",
    )
    require(
        attestation.get("stage_admission_run_id") == stage_run_id,
        "attestation Stage run mismatch",
    )
    verifier = attestation.get("verifier")
    require(
        isinstance(verifier, str) and verifier and not verifier.endswith("[bot]"),
        "verifier must be a human GitHub actor",
    )
    verification_run_id = attestation.get("evidence_verification_run_id")
    require(
        isinstance(verification_run_id, str) and verification_run_id.isdigit(),
        "evidence_verification_run_id invalid",
    )
    verified_at = parse_timestamp(attestation.get("verified_at"), "attestation verified_at")
    require(verified_at >= observed_at, "attestation predates observation")

    for field, path in (
        ("stage_attestation_sha256", stage_path),
        ("evidence_observation_sha256", observation_path),
    ):
        value = attestation.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(value == digest(path), f"{field} mismatch")

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "verification_id": verification_id,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
