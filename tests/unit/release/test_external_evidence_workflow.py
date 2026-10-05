from pathlib import Path


def test_external_evidence_workflow_uses_protected_synthetic_contract() -> None:
    workflow = Path(
        ".github/workflows/external-evidence-integration.yml"
    ).read_text(encoding="utf-8")

    assert "environment: production" in workflow
    assert "VERIFY_EVIDENCE" in workflow
    assert "HAMOON_EVIDENCE_S3_ENDPOINT" in workflow
    assert "HAMOON_EVIDENCE_S3_ACCESS_KEY" in workflow
    assert "HAMOON_EVIDENCE_S3_SECRET_KEY" in workflow
    assert "HAMOON_EVIDENCE_SCANNER_ENDPOINT" in workflow
    assert "HAMOON_EVIDENCE_SCANNER_TOKEN" in workflow
    assert "hamoon-stage-admission-$PROMOTED_SHA" in workflow
    assert "scripts/execute_evidence_integration_verification.py" in workflow
    assert "scripts/verify_external_evidence_integration.py" in workflow
    assert "evidence-integration-observation.json" in workflow
    assert "external_evidence_integration_verified" in workflow
    assert "evidence_observation_sha256" in workflow
