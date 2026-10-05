#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"recovery policy invalid: {message}")


def main() -> None:
    require(len(sys.argv) == 3, "usage: verify_recovery_policy.py <policy.json> <repo-root>")
    policy_path = Path(sys.argv[1]).resolve()
    repo_root = Path(sys.argv[2]).resolve()
    require(policy_path.is_file(), "policy file missing")
    value = json.loads(policy_path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "policy must be an object")
    require(value.get("schema_version") == 1, "unsupported schema")
    require(value.get("status") == "ENFORCED", "status must be ENFORCED")
    require(value.get("rehearsal_scope") == "STAGE_RECOVERY_REHEARSAL", "rehearsal_scope invalid")

    assets = value.get("required_assets")
    require(isinstance(assets, list), "required_assets missing")
    by_id = {
        item.get("id"): item
        for item in assets
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    require(set(by_id) == {"postgresql", "evidence_object_storage", "release_bundle"}, "required recovery asset set invalid")
    require(by_id["postgresql"].get("restore_test") == "required", "PostgreSQL restore test must be required")
    require(by_id["evidence_object_storage"].get("restore_test") == "required", "evidence restore test must be required")
    require(by_id["release_bundle"].get("restore_test") == "integrity_required", "release bundle integrity test must be required")

    assertions = value.get("required_stage_assertions")
    require(isinstance(assertions, list), "required_stage_assertions missing")
    expected_assertions = {
        "postgresql_backup_restored",
        "postgresql_schema_verified",
        "postgresql_probe_verified",
        "evidence_backup_restored",
        "evidence_probe_verified",
        "release_bundle_integrity_verified",
    }
    require(set(assertions) == expected_assertions, "stage assertion set invalid")

    forbidden = value.get("production_claims_forbidden_from_stage")
    require(isinstance(forbidden, list), "forbidden Production claims missing")
    require(
        set(forbidden) == {
            "production_managed_backup_verified",
            "production_pitr_verified",
            "external_backup_retention_verified",
        },
        "forbidden Production claim set invalid",
    )

    conditional = value.get("conditional_production_recovery_assets")
    require(isinstance(conditional, list), "conditional assets missing")
    conditional_ids = {
        item.get("id")
        for item in conditional
        if isinstance(item, dict) and item.get("required_when") == "self_hosted"
    }
    require(
        conditional_ids == {
            "nats_jetstream",
            "temporal_persistence",
            "keycloak_database_and_config",
        },
        "conditional self-hosted recovery assets invalid",
    )

    require(
        value.get("rpo_rto_policy_status")
        == "EXPLICIT_HUMAN_APPROVAL_REQUIRED",
        "RPO/RTO status must require explicit human approval",
    )
    objective_assets = value.get("required_recovery_objective_assets")
    require(
        isinstance(objective_assets, list)
        and set(objective_assets)
        == {"postgresql", "evidence_object_storage"},
        "required recovery objective asset set invalid",
    )
    objective_approval = value.get("recovery_objectives_approval")
    require(
        isinstance(objective_approval, dict),
        "recovery_objectives_approval missing",
    )
    require(
        objective_approval.get("workflow")
        == ".github/workflows/recovery-objectives-approval.yml",
        "recovery objectives approval workflow invalid",
    )
    require(
        objective_approval.get("artifact_prefix")
        == "hamoon-recovery-objectives-",
        "recovery objectives artifact prefix invalid",
    )
    require(
        objective_approval.get("approval_scope")
        == "PRODUCTION_RECOVERY_OBJECTIVES",
        "recovery objectives approval scope invalid",
    )
    require(
        objective_approval.get("authorization_only") is True,
        "recovery objectives approval must be authorization-only",
    )
    require(
        objective_approval.get("requires_successful_stage_rehearsal")
        is True,
        "recovery objectives approval must require Stage rehearsal",
    )
    workflow_path = objective_approval.get("workflow")
    require(
        isinstance(workflow_path, str)
        and (repo_root / workflow_path).is_file(),
        "recovery objectives approval workflow missing",
    )
    runbook = value.get("runbook")
    require(isinstance(runbook, str) and runbook, "runbook missing")
    require((repo_root / runbook).is_file(), f"runbook missing: {runbook}")

    print(json.dumps({
        "status": "valid",
        "asset_count": len(assets),
        "rpo_rto_policy_status": value["rpo_rto_policy_status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
