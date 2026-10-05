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
    assert "scripts/verify_production_deployment.py" in workflow
    assert "hamoon-production-deployment-${{ inputs.commit_sha }}" in workflow


def test_production_verification_requires_immutable_deployment_evidence() -> None:
    workflow = Path(".github/workflows/production-verification.yml").read_text(
        encoding="utf-8"
    )

    assert 'artifact_name="hamoon-production-deployment-$PROMOTED_SHA"' in workflow
    assert "scripts/verify_production_deployment.py" in workflow
    assert "production_deployment_run_id" in workflow
    assert "production_deployment_sha256" in workflow
