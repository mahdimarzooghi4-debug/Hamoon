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
    policy = tmp_path / "recovery-policy.json"
    _write_json(
        policy,
        {
            "status": "ENFORCED",
            "rpo_rto_policy_status": "EXPLICIT_HUMAN_APPROVAL_REQUIRED",
            "required_recovery_objective_assets": [
                "postgresql",
                "evidence_object_storage",
            ],
        },
    )

    rehearsal = tmp_path / "recovery-rehearsal.json"
    _write_json(
        rehearsal,
        {
            "status": "PASSED",
            "verification_scope": "STAGE_BACKUP_RESTORE",
            "production_managed_backup_verified": False,
            "production_pitr_verified": False,
            "external_backup_retention_verified": False,
            "commit_sha": COMMIT,
            "recovery_rehearsal_run_id": "404",
        },
    )

    approval = tmp_path / "recovery-objectives-approval.json"
    _write_json(
        approval,
        {
            "schema_version": 1,
            "status": "APPROVED",
            "approval_scope": "PRODUCTION_RECOVERY_OBJECTIVES",
            "authorization_only": True,
            "production_recovery_verified": False,
            "production_managed_backup_verified": False,
            "production_pitr_verified": False,
            "external_backup_retention_verified": False,
            "commit_sha": COMMIT,
            "recovery_rehearsal_run_id": "404",
            "recovery_objectives_approval_run_id": "505",
            "recovery_policy_sha256": hashlib.sha256(
                policy.read_bytes()
            ).hexdigest(),
            "recovery_rehearsal_sha256": hashlib.sha256(
                rehearsal.read_bytes()
            ).hexdigest(),
            "stage_rehearsal_status": "PASSED",
            "objectives": {
                "postgresql": {
                    "rpo_minutes": 15,
                    "rto_minutes": 60,
                },
                "evidence_object_storage": {
                    "rpo_minutes": 60,
                    "rto_minutes": 120,
                },
            },
            "approver": "operations-admin",
            "triggering_actor": "operations-admin",
            "change_reference": "OPS-RECOVERY-001",
            "approval_note": "Approved recovery objectives.",
            "approved_at": "2026-10-05T03:00:00+00:00",
        },
    )
    return policy, rehearsal, approval


def _verify(
    policy: Path,
    rehearsal: Path,
    approval: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_recovery_objectives.py",
            str(policy),
            str(rehearsal),
            str(approval),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_recovery_objectives_accept_human_approved_targets(
    tmp_path: Path,
) -> None:
    result = _verify(*_chain(tmp_path))

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_recovery_objectives_reject_bot_approver(tmp_path: Path) -> None:
    policy, rehearsal, approval = _chain(tmp_path)
    value = json.loads(approval.read_text())
    value["approver"] = "recovery-bot[bot]"
    _write_json(approval, value)

    result = _verify(policy, rehearsal, approval)

    assert result.returncode != 0
    assert "human GitHub actor" in result.stderr


def test_recovery_objectives_reject_zero_target(tmp_path: Path) -> None:
    policy, rehearsal, approval = _chain(tmp_path)
    value = json.loads(approval.read_text())
    value["objectives"]["postgresql"]["rpo_minutes"] = 0
    _write_json(approval, value)

    result = _verify(policy, rehearsal, approval)

    assert result.returncode != 0
    assert "positive integer" in result.stderr


def test_recovery_objectives_reject_tampered_rehearsal(
    tmp_path: Path,
) -> None:
    policy, rehearsal, approval = _chain(tmp_path)
    rehearsal.write_text(rehearsal.read_text() + " ", encoding="utf-8")

    result = _verify(policy, rehearsal, approval)

    assert result.returncode != 0
    assert "recovery_rehearsal_sha256 mismatch" in result.stderr


def test_recovery_objectives_cannot_claim_production_recovery(
    tmp_path: Path,
) -> None:
    policy, rehearsal, approval = _chain(tmp_path)
    value = json.loads(approval.read_text())
    value["production_recovery_verified"] = True
    _write_json(approval, value)

    result = _verify(policy, rehearsal, approval)

    assert result.returncode != 0
    assert "must not claim Production recovery verification" in result.stderr
