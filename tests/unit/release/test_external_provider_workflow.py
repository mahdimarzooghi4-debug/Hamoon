from pathlib import Path


def test_external_provider_workflow_uses_protected_synthetic_contract() -> None:
    workflow = Path(
        ".github/workflows/external-provider-integration.yml"
    ).read_text(encoding="utf-8")

    assert "environment: production" in workflow
    assert "VERIFY_PROVIDER" in workflow
    assert "HAMOON_PROVIDER_DISPATCH_CONFIG" in workflow
    assert "scripts/execute_provider_integration_verification.py" in workflow
    assert "scripts/verify_external_provider_integration.py" in workflow
    assert "hamoon-stage-admission-$PROMOTED_SHA" in workflow
    assert "provider-verification-request.json" in workflow
    assert "provider-verification-receipt.json" in workflow
    assert "external_provider_integration_verified" in workflow
    assert "provider_verification_request_sha256" in workflow
    assert "provider_verification_receipt_sha256" in workflow
