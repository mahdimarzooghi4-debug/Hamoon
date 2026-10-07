from pathlib import Path


def test_production_deploy_workflow_requires_protected_orchestrator_contract() -> None:
    workflow = Path(".github/workflows/production-deploy.yml").read_text(
        encoding="utf-8"
    )

    assert "environment: production" in workflow
    assert (
        "HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT: "
        "${{ secrets.HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT }}"
        in workflow
    )
    assert (
        "HAMOON_DEPLOY_ORCHESTRATOR_TOKEN: "
        "${{ secrets.HAMOON_DEPLOY_ORCHESTRATOR_TOKEN }}"
        in workflow
    )
    assert "scripts/execute_production_deployment.py" in workflow
    assert "ops/production/runtime-preflight.json" in workflow
    assert "preflight-request.json" in workflow
    assert "preflight-receipt.json" in workflow
    assert "runtime_preflight_contract_sha256" in workflow
    assert "preflight_request_sha256" in workflow
    assert "preflight_receipt_sha256" in workflow
    assert "preflight_id" in workflow
    assert "scripts/verify_production_deployment.py" in workflow
    assert "OPERATIONAL_READINESS_RUN_ID" in workflow
    assert "hamoon-production-operational-readiness-$PROMOTED_SHA" in workflow
    assert "deployment-input/readiness/production-operational-readiness.json" in workflow
    assert "hamoon-production-deployment-${{ inputs.commit_sha }}" in workflow


def test_production_verification_requires_immutable_deployment_evidence() -> None:
    workflow = Path(".github/workflows/production-verification.yml").read_text(
        encoding="utf-8"
    )

    assert 'artifact_name="hamoon-production-deployment-$PROMOTED_SHA"' in workflow
    assert "scripts/verify_production_deployment.py" in workflow
    assert "verification-input/deployment/preflight-request.json" in workflow
    assert "verification-input/deployment/preflight-receipt.json" in workflow
    assert "ops/production/runtime-preflight.json" in workflow
    assert "production_deployment_run_id" in workflow
    assert "production_deployment_sha256" in workflow


def test_production_admission_requires_operational_readiness_evidence() -> None:
    workflow = Path(
        ".github/workflows/production-deployment-admission.yml"
    ).read_text(encoding="utf-8")

    assert "Resolve immutable Production Operational Readiness artifact" in workflow
    assert "OPERATIONAL_READINESS_RUN_ID" in workflow
    assert "hamoon-production-operational-readiness-$PROMOTED_SHA" in workflow
    assert "operational_readiness_sha256" in workflow
    assert "operational_readiness_status" in workflow
    assert "admission-input/readiness/production-operational-readiness.json" in workflow
