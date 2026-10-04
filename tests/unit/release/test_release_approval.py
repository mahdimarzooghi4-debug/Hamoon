from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40
API_IMAGE_ID = "sha256:" + "b" * 64
WEB_IMAGE_ID = "sha256:" + "c" * 64


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _bundle(tmp_path: Path) -> tuple[Path, Path, Path]:
    release = tmp_path / "release"
    release.mkdir()
    manifest_path = release / "manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": 2,
            "repository": "owner/Hamoon",
            "commit_sha": COMMIT,
            "workflow_run_id": "101",
            "backend": {"image_id": API_IMAGE_ID},
            "frontend": {"image_id": WEB_IMAGE_ID},
        },
    )

    stage_path = tmp_path / "stage-attestation.json"
    _write_json(
        stage_path,
        {
            "schema_version": 1,
            "status": "PASSED",
            "commit_sha": COMMIT,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
        },
    )

    approval_path = tmp_path / "release-approval.json"
    _write_json(
        approval_path,
        {
            "schema_version": 1,
            "status": "APPROVED",
            "approval_scope": "RELEASE_TO_PRODUCTION",
            "authorization_only": True,
            "production_deployed": False,
            "commit_sha": COMMIT,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
            "release_manifest_sha256": hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest(),
            "stage_attestation_sha256": hashlib.sha256(
                stage_path.read_bytes()
            ).hexdigest(),
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "approver": "release-admin",
            "triggering_actor": "release-admin",
            "approval_run_id": "303",
            "change_reference": "REL-2026-001",
            "approval_note": "Stage evidence reviewed.",
            "approved_at": "2026-10-04T16:40:00+00:00",
            "stage_status": "PASSED",
        },
    )
    return release, stage_path, approval_path


def _verify(
    release: Path,
    stage: Path,
    approval: Path,
) -> subprocess.CompletedProcess[str]:
    script = Path("scripts/verify_release_approval.py")
    return subprocess.run(
        [sys.executable, str(script), str(release), str(stage), str(approval)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_release_approval_verifier_accepts_bound_human_approval(
    tmp_path: Path,
) -> None:
    release, stage, approval = _bundle(tmp_path)

    result = _verify(release, stage, approval)

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_release_approval_verifier_rejects_tampered_stage_attestation(
    tmp_path: Path,
) -> None:
    release, stage, approval = _bundle(tmp_path)
    stage.write_text(stage.read_text() + " ", encoding="utf-8")

    result = _verify(release, stage, approval)

    assert result.returncode != 0
    assert "Stage attestation SHA-256 mismatch" in result.stderr


def test_release_approval_verifier_rejects_bot_approver(
    tmp_path: Path,
) -> None:
    release, stage, approval = _bundle(tmp_path)
    value = json.loads(approval.read_text())
    value["approver"] = "release-bot[bot]"
    _write_json(approval, value)

    result = _verify(release, stage, approval)

    assert result.returncode != 0
    assert "approver must be a human GitHub actor" in result.stderr
