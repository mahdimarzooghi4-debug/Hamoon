from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40
DEPLOYMENT = "prod-deploy-42"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(tmp_path: Path, *, mode: str = "managed") -> tuple[Path, ...]:
    policy = tmp_path / "recovery-policy.json"
    _write_json(
        policy,
        {
            "status": "ENFORCED",
            "required_recovery_objective_assets": [
                "postgresql",
                "evidence_object_storage",
            ],
            "conditional_production_recovery_assets": [
                {"id": "nats_jetstream", "required_when": "self_hosted"},
                {"id": "temporal_persistence", "required_when": "self_hosted"},
                {"id": "keycloak_database_and_config", "required_when": "self_hosted"},
            ],
            "production_recovery_verification": {
                "verification_scope": "PRODUCTION_BACKUP_RESTORE_PITR",
                "requires_remote_https_evidence": True,
                "forbidden_evidence_fields": [
                    "password",
                    "secret",
                    "token",
                    "credentials",
                    "private_key",
                    "access_key",
                    "secret_key",
                    "connection_string",
                ],
            },
        },
    )
    rehearsal = tmp_path / "recovery-rehearsal.json"
    _write_json(
        rehearsal,
        {
            "status": "PASSED",
            "verification_scope": "STAGE_BACKUP_RESTORE",
            "commit_sha": COMMIT,
            "recovery_rehearsal_run_id": "404",
        },
    )
    approval = tmp_path / "recovery-objectives-approval.json"
    _write_json(
        approval,
        {
            "status": "APPROVED",
            "approval_scope": "PRODUCTION_RECOVERY_OBJECTIVES",
            "authorization_only": True,
            "commit_sha": COMMIT,
            "recovery_rehearsal_run_id": "404",
            "recovery_objectives_approval_run_id": "505",
            "recovery_policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
            "recovery_rehearsal_sha256": hashlib.sha256(rehearsal.read_bytes()).hexdigest(),
            "objectives": {
                "postgresql": {"rpo_minutes": 15, "rto_minutes": 60},
                "evidence_object_storage": {"rpo_minutes": 60, "rto_minutes": 120},
            },
        },
    )
    monitoring = tmp_path / "production-monitoring.json"
    _write_json(
        monitoring,
        {
            "status": "BASELINE_PASSED",
            "production_deployed": True,
            "production_verified": True,
            "commit_sha": COMMIT,
            "deployment_id": DEPLOYMENT,
            "production_monitoring_run_id": "303",
        },
    )
    observation = tmp_path / "provider-observation.json"
    self_hosted_assets = None
    if mode == "self_hosted":
        self_hosted_assets = [
            {"id": "nats_jetstream", "backup_restored": True, "integrity_verified": True},
            {"id": "temporal_persistence", "backup_restored": True, "integrity_verified": True},
            {"id": "keycloak_database_and_config", "backup_restored": True, "integrity_verified": True},
        ]
    _write_json(
        observation,
        {
            "schema_version": 1,
            "verification_scope": "PRODUCTION_BACKUP_RESTORE_PITR",
            "provider": "provider-a",
            "query_origin": "https://recovery.example.com/evidence",
            "commit_sha": COMMIT,
            "deployment_id": DEPLOYMENT,
            "observed_at": "2026-10-05T04:00:00+00:00",
            "infrastructure_mode": mode,
            "postgresql": {
                "backup_enabled": True,
                "pitr_enabled": True,
                "retention_verified": True,
                "encryption_at_rest_verified": True,
                "restore_isolated": True,
                "schema_identity_verified": True,
                "critical_data_sanity_verified": True,
                "pitr_restore_verified": True,
                "latest_recoverable_point_at": "2026-10-05T03:50:00+00:00",
                "restore_started_at": "2026-10-05T02:00:00+00:00",
                "restore_completed_at": "2026-10-05T02:45:00+00:00",
            },
            "evidence_object_storage": {
                "backup_or_versioning_enabled": True,
                "retention_verified": True,
                "encryption_at_rest_verified": True,
                "restore_isolated": True,
                "integrity_verified": True,
                "critical_evidence_sanity_verified": True,
                "latest_recoverable_point_at": "2026-10-05T03:30:00+00:00",
                "restore_started_at": "2026-10-05T01:00:00+00:00",
                "restore_completed_at": "2026-10-05T02:30:00+00:00",
            },
            "self_hosted_assets": self_hosted_assets,
        },
    )
    attestation = tmp_path / "production-recovery.json"
    _write_json(
        attestation,
        {
            "schema_version": 1,
            "status": "VERIFIED",
            "verification_scope": "PRODUCTION_BACKUP_RESTORE_PITR",
            "production_recovery_verified": True,
            "production_backup_restore_verified": True,
            "production_pitr_verified": True,
            "external_backup_retention_verified": True,
            "recovery_objectives_met": True,
            "production_managed_backup_verified": mode == "managed",
            "self_hosted_recovery_assets_verified": mode == "self_hosted",
            "commit_sha": COMMIT,
            "deployment_id": DEPLOYMENT,
            "provider": "provider-a",
            "recovery_rehearsal_run_id": "404",
            "recovery_objectives_approval_run_id": "505",
            "production_monitoring_run_id": "303",
            "infrastructure_mode": mode,
            "postgresql_rpo_age_seconds": 600,
            "postgresql_rto_seconds": 2700,
            "evidence_rpo_age_seconds": 1800,
            "evidence_rto_seconds": 5400,
            "recovery_policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
            "recovery_rehearsal_sha256": hashlib.sha256(rehearsal.read_bytes()).hexdigest(),
            "recovery_objectives_approval_sha256": hashlib.sha256(approval.read_bytes()).hexdigest(),
            "production_monitoring_sha256": hashlib.sha256(monitoring.read_bytes()).hexdigest(),
            "provider_observation_sha256": hashlib.sha256(observation.read_bytes()).hexdigest(),
            "production_recovery_verification_run_id": "606",
            "verifier": "operations-admin",
            "verified_at": "2026-10-05T04:01:00+00:00",
        },
    )
    return policy, rehearsal, approval, monitoring, observation, attestation


def _verify(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/verify_production_recovery.py", *map(str, paths)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_production_recovery_accepts_managed_evidence(tmp_path: Path) -> None:
    result = _verify(*_chain(tmp_path))
    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_production_recovery_accepts_complete_self_hosted_evidence(tmp_path: Path) -> None:
    result = _verify(*_chain(tmp_path, mode="self_hosted"))
    assert result.returncode == 0


def test_production_recovery_rejects_rpo_breach(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    observation = chain[4]
    attestation = chain[5]
    value = json.loads(observation.read_text())
    value["postgresql"]["latest_recoverable_point_at"] = "2026-10-05T03:30:00+00:00"
    _write_json(observation, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["provider_observation_sha256"] = hashlib.sha256(
        observation.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "approved RPO exceeded" in result.stderr


def test_production_recovery_rejects_rto_breach(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    observation = chain[4]
    attestation = chain[5]
    value = json.loads(observation.read_text())
    value["evidence_object_storage"]["restore_completed_at"] = "2026-10-05T03:30:01+00:00"
    _write_json(observation, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["provider_observation_sha256"] = hashlib.sha256(
        observation.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "approved RTO exceeded" in result.stderr


def test_production_recovery_rejects_missing_self_hosted_asset(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path, mode="self_hosted"))
    observation = chain[4]
    attestation = chain[5]
    value = json.loads(observation.read_text())
    value["self_hosted_assets"].pop()
    _write_json(observation, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["provider_observation_sha256"] = hashlib.sha256(
        observation.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "self-hosted recovery asset set invalid" in result.stderr


def test_production_recovery_rejects_secret_fields(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    observation = chain[4]
    attestation = chain[5]
    value = json.loads(observation.read_text())
    value["token"] = "must-not-be-persisted"
    _write_json(observation, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["provider_observation_sha256"] = hashlib.sha256(
        observation.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "forbidden evidence fields present" in result.stderr
