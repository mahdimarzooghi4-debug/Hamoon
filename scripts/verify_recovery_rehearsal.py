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
        raise SystemExit(f"recovery rehearsal invalid: {message}")


def load_object(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"recovery rehearsal invalid: cannot parse {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain an object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    require(
        len(sys.argv) == 8,
        "usage: verify_recovery_rehearsal.py <policy> <release-dir> <stage-attestation> <backup-metadata> <postgres-dump> <evidence-archive> <recovery-attestation>",
    )
    policy_path = Path(sys.argv[1]).resolve()
    release_dir = Path(sys.argv[2]).resolve()
    stage_path = Path(sys.argv[3]).resolve()
    metadata_path = Path(sys.argv[4]).resolve()
    postgres_dump = Path(sys.argv[5]).resolve()
    evidence_archive = Path(sys.argv[6]).resolve()
    attestation_path = Path(sys.argv[7]).resolve()

    policy = load_object(policy_path)
    manifest_path = release_dir / "manifest.json"
    manifest = load_object(manifest_path)
    stage = load_object(stage_path)
    metadata = load_object(metadata_path)
    attestation = load_object(attestation_path)
    require(postgres_dump.is_file(), "PostgreSQL backup file missing")
    require(evidence_archive.is_file(), "evidence backup archive missing")

    require(policy.get("status") == "ENFORCED", "policy not enforced")
    require(policy.get("rehearsal_scope") == "STAGE_RECOVERY_REHEARSAL", "policy rehearsal scope invalid")
    require(stage.get("status") == "PASSED", "Stage admission not passed")
    require(attestation.get("schema_version") == 1, "unsupported schema")
    require(attestation.get("status") == "PASSED", "status must be PASSED")
    require(attestation.get("verification_scope") == "STAGE_BACKUP_RESTORE", "verification_scope invalid")
    require(attestation.get("production_managed_backup_verified") is False, "Stage must not claim managed Production backup verification")
    require(attestation.get("production_pitr_verified") is False, "Stage must not claim Production PITR verification")
    require(attestation.get("external_backup_retention_verified") is False, "Stage must not claim external backup retention verification")

    commit_sha = attestation.get("commit_sha")
    require(isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None, "commit_sha invalid")
    require(commit_sha == manifest.get("commit_sha"), "release commit mismatch")
    require(commit_sha == stage.get("commit_sha"), "Stage commit mismatch")

    for field in ("source_ci_run_id", "stage_admission_run_id", "recovery_rehearsal_run_id"):
        value = attestation.get(field)
        require(isinstance(value, str) and value.isdigit(), f"{field} invalid")
    require(attestation["source_ci_run_id"] == stage.get("source_ci_run_id"), "source CI run mismatch")
    require(attestation["stage_admission_run_id"] == stage.get("stage_admission_run_id"), "Stage run mismatch")

    for field in (
        "postgresql_backup_restored",
        "postgresql_schema_verified",
        "postgresql_probe_verified",
        "evidence_backup_restored",
        "evidence_probe_verified",
        "release_bundle_integrity_verified",
    ):
        require(attestation.get(field) is True, f"{field} must be true")

    for field, path in (
        ("policy_sha256", policy_path),
        ("release_manifest_sha256", manifest_path),
        ("stage_attestation_sha256", stage_path),
        ("backup_metadata_sha256", metadata_path),
        ("postgres_dump_sha256", postgres_dump),
        ("evidence_archive_sha256", evidence_archive),
    ):
        value = attestation.get(field)
        require(isinstance(value, str) and SHA256_RE.fullmatch(value) is not None, f"{field} invalid")
        require(value == sha256(path), f"{field} mismatch")

    require(metadata.get("postgres_dump_sha256") == sha256(postgres_dump), "metadata PostgreSQL hash mismatch")
    require(metadata.get("evidence_archive_sha256") == sha256(evidence_archive), "metadata evidence hash mismatch")
    for field in ("postgres_dump_bytes", "evidence_archive_bytes"):
        value = metadata.get(field)
        require(isinstance(value, int) and value > 0, f"{field} invalid")

    source_versions = metadata.get("source_alembic_versions")
    restored_versions = metadata.get("restored_alembic_versions")
    require(
        isinstance(source_versions, list)
        and source_versions
        and all(isinstance(item, str) and item for item in source_versions),
        "source Alembic versions invalid",
    )
    require(restored_versions == source_versions, "restored Alembic versions differ from source")

    source_probe_sha = metadata.get("source_evidence_probe_sha256")
    restored_probe_sha = metadata.get("restored_evidence_probe_sha256")
    require(isinstance(source_probe_sha, str) and SHA256_RE.fullmatch(source_probe_sha) is not None, "source evidence probe hash invalid")
    require(restored_probe_sha == source_probe_sha, "restored evidence probe differs from source")
    require(metadata.get("postgres_probe_restored") is True, "PostgreSQL probe was not restored")

    verified_at = attestation.get("verified_at")
    require(isinstance(verified_at, str), "verified_at missing")
    try:
        timestamp = datetime.fromisoformat(verified_at)
    except ValueError as exc:
        raise SystemExit("recovery rehearsal invalid: verified_at invalid") from exc
    require(timestamp.tzinfo is not None, "verified_at must include timezone")

    print(json.dumps({
        "status": "valid",
        "commit_sha": commit_sha,
        "postgres_dump_bytes": metadata["postgres_dump_bytes"],
        "evidence_archive_bytes": metadata["evidence_archive_bytes"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
