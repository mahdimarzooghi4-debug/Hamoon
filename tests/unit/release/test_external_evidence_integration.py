from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(tmp_path: Path) -> tuple[Path, Path, Path]:
    stage = tmp_path / "stage-attestation.json"
    _write_json(
        stage,
        {
            "schema_version": 1,
            "status": "PASSED",
            "commit_sha": COMMIT,
            "stage_admission_run_id": "202",
        },
    )

    observation = tmp_path / "evidence-integration-observation.json"
    _write_json(
        observation,
        {
            "schema_version": 1,
            "status": "VERIFIED",
            "verification_scope": "EXTERNAL_EVIDENCE_STORAGE_SCANNER",
            "verification_id": "hamoon-evidence-verify-test",
            "commit_sha": COMMIT,
            "synthetic": True,
            "contains_pii": False,
            "object_sha256": (
                "2e1fdb7035fa524273cbac5fc9a0cbec"
                "448af449cf33e120bbf926688a1f84d5"
            ),
            "object_size_bytes": 44,
            "checks": {
                "storage_put": True,
                "storage_metadata_integrity": True,
                "storage_signed_read_integrity": True,
                "storage_anonymous_read_denied": True,
                "scanner_clean": True,
                "storage_cleanup": True,
            },
            "verified_at": "2026-10-05T13:00:00+00:00",
        },
    )

    attestation = tmp_path / "evidence-integration-verification.json"
    _write_json(
        attestation,
        {
            "schema_version": 1,
            "status": "VERIFIED",
            "verification_scope": "EXTERNAL_EVIDENCE_STORAGE_SCANNER",
            "external_evidence_integration_verified": True,
            "commit_sha": COMMIT,
            "verification_id": "hamoon-evidence-verify-test",
            "stage_admission_run_id": "202",
            "evidence_verification_run_id": "303",
            "stage_attestation_sha256": hashlib.sha256(
                stage.read_bytes()
            ).hexdigest(),
            "evidence_observation_sha256": hashlib.sha256(
                observation.read_bytes()
            ).hexdigest(),
            "verifier": "production-operator",
            "verified_at": "2026-10-05T13:01:00+00:00",
        },
    )
    return stage, observation, attestation


def _verify(
    stage: Path,
    observation: Path,
    attestation: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_external_evidence_integration.py",
            str(stage),
            str(observation),
            str(attestation),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_external_evidence_verifier_accepts_bound_observation(
    tmp_path: Path,
) -> None:
    result = _verify(*_chain(tmp_path))

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_external_evidence_verifier_rejects_tampered_observation(
    tmp_path: Path,
) -> None:
    stage, observation, attestation = _chain(tmp_path)
    observation.write_text(observation.read_text() + " ", encoding="utf-8")

    result = _verify(stage, observation, attestation)

    assert result.returncode != 0
    assert "evidence_observation_sha256 mismatch" in result.stderr


def test_external_evidence_verifier_rejects_sensitive_fields(
    tmp_path: Path,
) -> None:
    stage, observation, attestation = _chain(tmp_path)
    value = json.loads(observation.read_text())
    value["storage_key"] = "_hamoon-verification/secret"
    _write_json(observation, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["evidence_observation_sha256"] = hashlib.sha256(
        observation.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)

    result = _verify(stage, observation, attestation)

    assert result.returncode != 0
    assert "forbidden evidence fields present" in result.stderr


def test_external_evidence_verifier_rejects_failed_cleanup(
    tmp_path: Path,
) -> None:
    stage, observation, attestation = _chain(tmp_path)
    value = json.loads(observation.read_text())
    value["checks"]["storage_cleanup"] = False
    _write_json(observation, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["evidence_observation_sha256"] = hashlib.sha256(
        observation.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)

    result = _verify(stage, observation, attestation)

    assert result.returncode != 0
    assert "required check failed: storage_cleanup" in result.stderr
