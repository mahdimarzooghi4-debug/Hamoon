#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DEPLOYMENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"production recovery invalid: {message}")


def load_object(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"production recovery invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain an object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_timestamp(value: object, field: str) -> datetime:
    require(isinstance(value, str), f"{field} missing")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(
            f"production recovery invalid: {field} invalid"
        ) from exc
    require(timestamp.tzinfo is not None, f"{field} must include timezone")
    return timestamp


def remote_https(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or parsed.hostname is None:
        return False
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_unspecified
    )


def recursive_keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            found.add(str(key).lower())
            found.update(recursive_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(recursive_keys(nested))
    return found


def positive_minutes(value: object, field: str) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool) and value > 0,
        f"{field} must be a positive integer",
    )
    return value


def require_restore_window(
    *,
    asset: dict[str, object],
    asset_name: str,
    observed_at: datetime,
    rpo_minutes: int,
    rto_minutes: int,
) -> tuple[int, int]:
    latest = parse_timestamp(
        asset.get("latest_recoverable_point_at"),
        f"{asset_name}.latest_recoverable_point_at",
    )
    require(latest <= observed_at, f"{asset_name} recovery point is in the future")
    rpo_age_seconds = int((observed_at - latest).total_seconds())
    require(rpo_age_seconds >= 0, f"{asset_name} RPO age invalid")
    require(
        rpo_age_seconds <= rpo_minutes * 60,
        f"{asset_name} approved RPO exceeded",
    )

    started = parse_timestamp(
        asset.get("restore_started_at"),
        f"{asset_name}.restore_started_at",
    )
    completed = parse_timestamp(
        asset.get("restore_completed_at"),
        f"{asset_name}.restore_completed_at",
    )
    require(completed >= started, f"{asset_name} restore window invalid")
    rto_seconds = int((completed - started).total_seconds())
    require(
        rto_seconds <= rto_minutes * 60,
        f"{asset_name} approved RTO exceeded",
    )
    return rpo_age_seconds, rto_seconds


def main() -> None:
    require(
        len(sys.argv) == 7,
        (
            "usage: verify_production_recovery.py <recovery-policy> "
            "<recovery-rehearsal> <objectives-approval> "
            "<production-monitoring> <provider-observation> <attestation>"
        ),
    )
    policy_path = Path(sys.argv[1]).resolve()
    rehearsal_path = Path(sys.argv[2]).resolve()
    approval_path = Path(sys.argv[3]).resolve()
    monitoring_path = Path(sys.argv[4]).resolve()
    observation_path = Path(sys.argv[5]).resolve()
    attestation_path = Path(sys.argv[6]).resolve()

    policy = load_object(policy_path)
    rehearsal = load_object(rehearsal_path)
    approval = load_object(approval_path)
    monitoring = load_object(monitoring_path)
    observation = load_object(observation_path)
    attestation = load_object(attestation_path)

    require(policy.get("status") == "ENFORCED", "recovery policy not enforced")
    production_policy = policy.get("production_recovery_verification")
    require(isinstance(production_policy, dict), "production recovery policy missing")
    require(
        production_policy.get("verification_scope")
        == "PRODUCTION_BACKUP_RESTORE_PITR",
        "production recovery scope invalid",
    )
    require(
        production_policy.get("requires_remote_https_evidence") is True,
        "remote evidence must be required",
    )

    require(rehearsal.get("status") == "PASSED", "recovery rehearsal not passed")
    require(
        rehearsal.get("verification_scope") == "STAGE_BACKUP_RESTORE",
        "recovery rehearsal scope invalid",
    )
    require(approval.get("status") == "APPROVED", "recovery objectives not approved")
    require(
        approval.get("approval_scope") == "PRODUCTION_RECOVERY_OBJECTIVES",
        "recovery objectives scope invalid",
    )
    require(
        approval.get("authorization_only") is True,
        "recovery objectives approval must remain authorization-only",
    )

    commit_sha = approval.get("commit_sha")
    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "commit_sha invalid",
    )
    require(rehearsal.get("commit_sha") == commit_sha, "rehearsal commit mismatch")
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
        rehearsal.get("recovery_rehearsal_run_id") == rehearsal_run_id,
        "recovery rehearsal run mismatch",
    )
    require(
        approval.get("recovery_rehearsal_sha256") == digest(rehearsal_path),
        "recovery rehearsal hash mismatch",
    )
    require(
        approval.get("recovery_policy_sha256") == digest(policy_path),
        "recovery policy hash mismatch",
    )

    require(
        monitoring.get("status") == "BASELINE_PASSED",
        "Production monitoring baseline not passed",
    )
    require(monitoring.get("production_deployed") is True, "Production not deployed")
    require(monitoring.get("production_verified") is True, "Production not verified")
    require(monitoring.get("commit_sha") == commit_sha, "monitoring commit mismatch")
    monitoring_run_id = monitoring.get("production_monitoring_run_id")
    require(
        isinstance(monitoring_run_id, str) and monitoring_run_id.isdigit(),
        "production_monitoring_run_id invalid",
    )
    deployment_id = monitoring.get("deployment_id")
    require(
        isinstance(deployment_id, str)
        and DEPLOYMENT_ID_RE.fullmatch(deployment_id) is not None,
        "monitoring deployment invalid",
    )

    require(observation.get("schema_version") == 1, "observation schema unsupported")
    require(
        observation.get("verification_scope") == "PRODUCTION_BACKUP_RESTORE_PITR",
        "observation scope invalid",
    )
    require(remote_https(observation.get("query_origin")), "query_origin must be remote HTTPS")
    provider = observation.get("provider")
    require(isinstance(provider, str) and provider.strip(), "provider missing")
    require(observation.get("commit_sha") == commit_sha, "observation commit mismatch")
    require(
        observation.get("deployment_id") == deployment_id,
        "observation deployment mismatch",
    )
    observed_at = parse_timestamp(observation.get("observed_at"), "observed_at")

    forbidden = production_policy.get("forbidden_evidence_fields")
    require(isinstance(forbidden, list), "forbidden evidence fields missing")
    forbidden_keys = {str(value).lower() for value in forbidden}
    leaked = forbidden_keys & recursive_keys(observation)
    require(not leaked, f"forbidden evidence fields present {sorted(leaked)}")

    objectives = approval.get("objectives")
    require(isinstance(objectives, dict), "approved objectives missing")
    required_assets = policy.get("required_recovery_objective_assets")
    require(
        isinstance(required_assets, list)
        and set(required_assets) == {"postgresql", "evidence_object_storage"},
        "required recovery objective assets invalid",
    )

    pg_objective = objectives.get("postgresql")
    evidence_objective = objectives.get("evidence_object_storage")
    require(isinstance(pg_objective, dict), "PostgreSQL objective missing")
    require(isinstance(evidence_objective, dict), "evidence objective missing")
    pg_rpo = positive_minutes(pg_objective.get("rpo_minutes"), "postgresql.rpo_minutes")
    pg_rto = positive_minutes(pg_objective.get("rto_minutes"), "postgresql.rto_minutes")
    evidence_rpo = positive_minutes(
        evidence_objective.get("rpo_minutes"),
        "evidence_object_storage.rpo_minutes",
    )
    evidence_rto = positive_minutes(
        evidence_objective.get("rto_minutes"),
        "evidence_object_storage.rto_minutes",
    )

    pg = observation.get("postgresql")
    require(isinstance(pg, dict), "PostgreSQL evidence missing")
    for field in (
        "backup_enabled",
        "pitr_enabled",
        "retention_verified",
        "encryption_at_rest_verified",
        "restore_isolated",
        "schema_identity_verified",
        "critical_data_sanity_verified",
        "pitr_restore_verified",
    ):
        require(pg.get(field) is True, f"postgresql.{field} must be true")
    pg_rpo_seconds, pg_rto_seconds = require_restore_window(
        asset=pg,
        asset_name="postgresql",
        observed_at=observed_at,
        rpo_minutes=pg_rpo,
        rto_minutes=pg_rto,
    )

    evidence = observation.get("evidence_object_storage")
    require(isinstance(evidence, dict), "evidence object storage proof missing")
    for field in (
        "backup_or_versioning_enabled",
        "retention_verified",
        "encryption_at_rest_verified",
        "restore_isolated",
        "integrity_verified",
        "critical_evidence_sanity_verified",
    ):
        require(
            evidence.get(field) is True,
            f"evidence_object_storage.{field} must be true",
        )
    evidence_rpo_seconds, evidence_rto_seconds = require_restore_window(
        asset=evidence,
        asset_name="evidence_object_storage",
        observed_at=observed_at,
        rpo_minutes=evidence_rpo,
        rto_minutes=evidence_rto,
    )

    infrastructure_mode = observation.get("infrastructure_mode")
    require(
        infrastructure_mode in {"managed", "self_hosted"},
        "infrastructure_mode invalid",
    )
    conditional_verified = False
    if infrastructure_mode == "self_hosted":
        expected_conditional = {
            item.get("id")
            for item in policy.get("conditional_production_recovery_assets", [])
            if isinstance(item, dict) and item.get("required_when") == "self_hosted"
        }
        require(
            expected_conditional
            == {"nats_jetstream", "temporal_persistence", "keycloak_database_and_config"},
            "conditional self-hosted asset policy invalid",
        )
        self_hosted_assets = observation.get("self_hosted_assets")
        require(isinstance(self_hosted_assets, list), "self-hosted recovery assets missing")
        by_id = {
            item.get("id"): item
            for item in self_hosted_assets
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        require(set(by_id) == expected_conditional, "self-hosted recovery asset set invalid")
        for asset_id in expected_conditional:
            item = by_id[asset_id]
            require(item.get("backup_restored") is True, f"{asset_id} backup not restored")
            require(item.get("integrity_verified") is True, f"{asset_id} integrity not verified")
        conditional_verified = True
    else:
        require(
            observation.get("self_hosted_assets") in (None, []),
            "managed recovery evidence must not claim self-hosted assets",
        )

    require(attestation.get("schema_version") == 1, "attestation schema unsupported")
    require(attestation.get("status") == "VERIFIED", "status must be VERIFIED")
    require(
        attestation.get("verification_scope") == "PRODUCTION_BACKUP_RESTORE_PITR",
        "attestation scope invalid",
    )
    require(
        attestation.get("production_recovery_verified") is True,
        "Production recovery must be verified",
    )
    require(
        attestation.get("production_backup_restore_verified") is True,
        "Production backup restore must be verified",
    )
    require(
        attestation.get("production_pitr_verified") is True,
        "Production PITR must be verified",
    )
    require(
        attestation.get("external_backup_retention_verified") is True,
        "external backup retention must be verified",
    )
    require(
        attestation.get("recovery_objectives_met") is True,
        "approved recovery objectives must be met",
    )
    require(attestation.get("commit_sha") == commit_sha, "attestation commit mismatch")
    require(
        attestation.get("deployment_id") == deployment_id,
        "attestation deployment mismatch",
    )
    require(attestation.get("provider") == provider, "attestation provider mismatch")
    require(
        attestation.get("recovery_rehearsal_run_id") == rehearsal_run_id,
        "attestation recovery rehearsal run mismatch",
    )
    require(
        attestation.get("recovery_objectives_approval_run_id") == approval_run_id,
        "attestation recovery objectives approval run mismatch",
    )
    require(
        attestation.get("production_monitoring_run_id") == monitoring_run_id,
        "attestation Production monitoring run mismatch",
    )
    require(
        attestation.get("infrastructure_mode") == infrastructure_mode,
        "attestation infrastructure mode mismatch",
    )
    require(
        attestation.get("production_managed_backup_verified")
        is (infrastructure_mode == "managed"),
        "managed backup claim does not match infrastructure mode",
    )
    require(
        attestation.get("self_hosted_recovery_assets_verified") is conditional_verified,
        "self-hosted recovery claim mismatch",
    )

    expected_metrics = {
        "postgresql_rpo_age_seconds": pg_rpo_seconds,
        "postgresql_rto_seconds": pg_rto_seconds,
        "evidence_rpo_age_seconds": evidence_rpo_seconds,
        "evidence_rto_seconds": evidence_rto_seconds,
    }
    for field, expected in expected_metrics.items():
        require(attestation.get(field) == expected, f"{field} mismatch")

    for field, path in (
        ("recovery_policy_sha256", policy_path),
        ("recovery_rehearsal_sha256", rehearsal_path),
        ("recovery_objectives_approval_sha256", approval_path),
        ("production_monitoring_sha256", monitoring_path),
        ("provider_observation_sha256", observation_path),
    ):
        value = attestation.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(value == digest(path), f"{field} mismatch")

    verifier = attestation.get("verifier")
    require(
        isinstance(verifier, str) and verifier and not verifier.endswith("[bot]"),
        "verifier must be a human GitHub actor",
    )
    verification_run_id = attestation.get("production_recovery_verification_run_id")
    require(
        isinstance(verification_run_id, str) and verification_run_id.isdigit(),
        "production_recovery_verification_run_id invalid",
    )
    verified_at = parse_timestamp(attestation.get("verified_at"), "verified_at")
    require(verified_at >= observed_at, "verified_at precedes provider observation")

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "deployment_id": deployment_id,
                "provider": provider,
                "infrastructure_mode": infrastructure_mode,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
