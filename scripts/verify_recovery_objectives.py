#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"recovery objectives invalid: {message}")


def load_object(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"recovery objectives invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain an object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def positive_minutes(value: object, field: str) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool) and value > 0,
        f"{field} must be a positive integer",
    )
    return value


def main() -> None:
    require(
        len(sys.argv) == 4,
        (
            "usage: verify_recovery_objectives.py "
            "<recovery-policy> <recovery-rehearsal> <objectives-approval>"
        ),
    )
    policy_path = Path(sys.argv[1]).resolve()
    rehearsal_path = Path(sys.argv[2]).resolve()
    approval_path = Path(sys.argv[3]).resolve()

    policy = load_object(policy_path)
    rehearsal = load_object(rehearsal_path)
    approval = load_object(approval_path)

    require(policy.get("status") == "ENFORCED", "recovery policy not enforced")
    require(
        policy.get("rpo_rto_policy_status")
        == "EXPLICIT_HUMAN_APPROVAL_REQUIRED",
        "policy does not require explicit objectives approval",
    )
    require(rehearsal.get("status") == "PASSED", "recovery rehearsal not passed")
    require(
        rehearsal.get("verification_scope") == "STAGE_BACKUP_RESTORE",
        "recovery rehearsal scope invalid",
    )
    require(
        rehearsal.get("production_managed_backup_verified") is False,
        "Stage rehearsal cannot prove managed Production backup",
    )
    require(
        rehearsal.get("production_pitr_verified") is False,
        "Stage rehearsal cannot prove Production PITR",
    )
    require(
        rehearsal.get("external_backup_retention_verified") is False,
        "Stage rehearsal cannot prove external backup retention",
    )

    require(approval.get("schema_version") == 1, "unsupported schema")
    require(approval.get("status") == "APPROVED", "status must be APPROVED")
    require(
        approval.get("approval_scope") == "PRODUCTION_RECOVERY_OBJECTIVES",
        "approval_scope invalid",
    )
    require(
        approval.get("authorization_only") is True,
        "approval must be authorization-only",
    )
    require(
        approval.get("production_recovery_verified") is False,
        "objectives approval must not claim Production recovery verification",
    )
    for field in (
        "production_managed_backup_verified",
        "production_pitr_verified",
        "external_backup_retention_verified",
    ):
        require(
            approval.get(field) is False,
            f"{field} must remain false in objectives approval",
        )

    commit_sha = approval.get("commit_sha")
    require(
        isinstance(commit_sha, str)
        and COMMIT_RE.fullmatch(commit_sha) is not None,
        "commit_sha invalid",
    )
    require(commit_sha == rehearsal.get("commit_sha"), "rehearsal commit mismatch")

    rehearsal_run_id = approval.get("recovery_rehearsal_run_id")
    approval_run_id = approval.get("recovery_objectives_approval_run_id")
    require(
        isinstance(rehearsal_run_id, str) and rehearsal_run_id.isdigit(),
        "recovery_rehearsal_run_id invalid",
    )
    require(
        isinstance(approval_run_id, str) and approval_run_id.isdigit(),
        "recovery_objectives_approval_run_id invalid",
    )
    require(
        rehearsal_run_id == rehearsal.get("recovery_rehearsal_run_id"),
        "recovery rehearsal run mismatch",
    )

    for field, path in (
        ("recovery_policy_sha256", policy_path),
        ("recovery_rehearsal_sha256", rehearsal_path),
    ):
        value = approval.get(field)
        require(
            isinstance(value, str)
            and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(value == digest(path), f"{field} mismatch")

    require(
        approval.get("stage_rehearsal_status") == "PASSED",
        "stage_rehearsal_status invalid",
    )

    objectives = approval.get("objectives")
    require(isinstance(objectives, dict), "objectives missing")
    expected_assets = policy.get("required_recovery_objective_assets")
    require(
        isinstance(expected_assets, list)
        and set(expected_assets)
        == {"postgresql", "evidence_object_storage"},
        "policy objective assets invalid",
    )
    require(set(objectives) == set(expected_assets), "objective asset set invalid")

    for asset in expected_assets:
        require(isinstance(asset, str), "objective asset id invalid")
        value = objectives.get(asset)
        require(isinstance(value, dict), f"{asset} objective missing")
        positive_minutes(value.get("rpo_minutes"), f"{asset}.rpo_minutes")
        positive_minutes(value.get("rto_minutes"), f"{asset}.rto_minutes")

    approver = approval.get("approver")
    require(
        isinstance(approver, str)
        and approver
        and not approver.endswith("[bot]"),
        "approver must be a human GitHub actor",
    )
    require(
        isinstance(approval.get("change_reference"), str)
        and str(approval["change_reference"]).strip(),
        "change_reference missing",
    )
    require(
        isinstance(approval.get("approval_note"), str)
        and str(approval["approval_note"]).strip(),
        "approval_note missing",
    )
    approved_at = approval.get("approved_at")
    require(isinstance(approved_at, str), "approved_at missing")
    try:
        timestamp = datetime.fromisoformat(approved_at)
    except ValueError as exc:
        raise SystemExit(
            "recovery objectives invalid: approved_at invalid"
        ) from exc
    require(timestamp.tzinfo is not None, "approved_at must include timezone")

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "approver": approver,
                "postgresql_rpo_minutes": objectives["postgresql"][
                    "rpo_minutes"
                ],
                "postgresql_rto_minutes": objectives["postgresql"][
                    "rto_minutes"
                ],
                "evidence_rpo_minutes": objectives[
                    "evidence_object_storage"
                ]["rpo_minutes"],
                "evidence_rto_minutes": objectives[
                    "evidence_object_storage"
                ]["rto_minutes"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
