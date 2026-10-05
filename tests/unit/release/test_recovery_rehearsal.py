from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    policy = tmp_path / "policy.json"
    _write_json(policy, {"schema_version": 1, "status": "ENFORCED", "rehearsal_scope": "STAGE_RECOVERY_REHEARSAL"})
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    manifest = release_dir / "manifest.json"
    _write_json(manifest, {"commit_sha": COMMIT, "workflow_run_id": "101"})
    stage = tmp_path / "stage.json"
    _write_json(stage, {"status": "PASSED", "commit_sha": COMMIT, "source_ci_run_id": "101", "stage_admission_run_id": "202"})
    postgres_dump = tmp_path / "postgres.dump"
    postgres_dump.write_bytes(b"postgres-backup")
    evidence_archive = tmp_path / "evidence.tar"
    evidence_archive.write_bytes(b"evidence-backup")
    probe_sha = hashlib.sha256(b"probe").hexdigest()
    metadata = tmp_path / "metadata.json"
    _write_json(metadata, {
        "postgres_dump_sha256": hashlib.sha256(postgres_dump.read_bytes()).hexdigest(),
        "postgres_dump_bytes": postgres_dump.stat().st_size,
        "evidence_archive_sha256": hashlib.sha256(evidence_archive.read_bytes()).hexdigest(),
        "evidence_archive_bytes": evidence_archive.stat().st_size,
        "source_alembic_versions": ["20261004_0026"],
        "restored_alembic_versions": ["20261004_0026"],
        "source_evidence_probe_sha256": probe_sha,
        "restored_evidence_probe_sha256": probe_sha,
        "postgres_probe_restored": True,
    })
    attestation = tmp_path / "attestation.json"
    _write_json(attestation, {
        "schema_version": 1,
        "status": "PASSED",
        "verification_scope": "STAGE_BACKUP_RESTORE",
        "production_managed_backup_verified": False,
        "production_pitr_verified": False,
        "external_backup_retention_verified": False,
        "commit_sha": COMMIT,
        "source_ci_run_id": "101",
        "stage_admission_run_id": "202",
        "recovery_rehearsal_run_id": "303",
        "postgresql_backup_restored": True,
        "postgresql_schema_verified": True,
        "postgresql_probe_verified": True,
        "evidence_backup_restored": True,
        "evidence_probe_verified": True,
        "release_bundle_integrity_verified": True,
        "policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
        "release_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "stage_attestation_sha256": hashlib.sha256(stage.read_bytes()).hexdigest(),
        "backup_metadata_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(),
        "postgres_dump_sha256": hashlib.sha256(postgres_dump.read_bytes()).hexdigest(),
        "evidence_archive_sha256": hashlib.sha256(evidence_archive.read_bytes()).hexdigest(),
        "verified_at": "2026-10-04T20:00:00+00:00",
    })
    return policy, release_dir, stage, metadata, postgres_dump, evidence_archive, attestation


def _verify(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/verify_recovery_rehearsal.py", *map(str, paths)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_recovery_rehearsal_accepts_exact_restore_evidence(tmp_path: Path) -> None:
    result = _verify(*_chain(tmp_path))
    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_recovery_rehearsal_rejects_false_production_backup_claim(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    attestation = chain[6]
    value = json.loads(attestation.read_text())
    value["production_managed_backup_verified"] = True
    _write_json(attestation, value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "must not claim managed Production backup" in result.stderr


def test_recovery_rehearsal_rejects_changed_restored_evidence(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    metadata = chain[3]
    attestation = chain[6]
    value = json.loads(metadata.read_text())
    value["restored_evidence_probe_sha256"] = hashlib.sha256(b"changed").hexdigest()
    _write_json(metadata, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["backup_metadata_sha256"] = hashlib.sha256(metadata.read_bytes()).hexdigest()
    _write_json(attestation, attestation_value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "restored evidence probe differs" in result.stderr

def test_recovery_workflow_waits_for_actual_database_query() -> None:
    repo_root = Path(__file__).parents[3]
    workflow = (
        repo_root / ".github/workflows/recovery-rehearsal.yml"
    ).read_text(encoding="utf-8")

    assert "-U hamoon -d hamoon -At -c 'SELECT 1'" in workflow
    assert "pg_isready -U hamoon -d hamoon" not in workflow

