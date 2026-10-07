from pathlib import Path


def test_deployment_docs_forbid_external_ai_runtime_contract() -> None:
    adr = Path("docs/ADR-008-HAMOON-DEPLOYMENT-PLATFORM.md").read_text(
        encoding="utf-8"
    )
    readme = Path("README.md").read_text(encoding="utf-8")

    forbidden = (
        "configured AI provider endpoints",
        "AI provider credentials",
        "AI provider key",
        "AI provider و object storage",
        "No AI provider call directly from arbitrary service",
        "real external AI/provider/storage integrations",
    )
    for marker in forbidden:
        assert marker not in adr
        assert marker not in readme

    assert "Production AI هیچ provider endpoint/token" in adr
    assert "Gemma فقط به‌صورت `IN_PROCESS` داخل Hamoon اجرا می‌شود." in adr
    assert "network model download" in adr
    assert "Production AI itself remains internal to Hamoon" in readme


def test_production_handoff_names_required_external_inputs() -> None:
    handoff = Path("docs/HAMOON_PRODUCTION_OPERATIONAL_HANDOFF.md").read_text(
        encoding="utf-8"
    )

    required = (
        "HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT",
        "HAMOON_DEPLOY_ORCHESTRATOR_TOKEN",
        "HAMOON_PRODUCTION_METRICS_TOKEN",
        "HAMOON_OBSERVABILITY_VERIFICATION_URL",
        "HAMOON_OBSERVABILITY_VERIFICATION_TOKEN",
        "HAMOON_ALERTMANAGER_URL",
        "HAMOON_ALERTMANAGER_METRICS_URL",
        "HAMOON_ALERTMANAGER_BEARER_TOKEN",
        "HAMOON_EVIDENCE_S3_ENDPOINT",
        "HAMOON_EVIDENCE_S3_ACCESS_KEY",
        "HAMOON_EVIDENCE_S3_SECRET_KEY",
        "HAMOON_EVIDENCE_S3_BUCKET",
        "HAMOON_EVIDENCE_S3_REGION",
        "HAMOON_EVIDENCE_SCANNER_ENDPOINT",
        "HAMOON_EVIDENCE_SCANNER_TOKEN",
        "HAMOON_PROVIDER_DISPATCH_CONFIG",
        "HAMOON_RECOVERY_VERIFICATION_URL",
        "HAMOON_RECOVERY_VERIFICATION_TOKEN",
        "HAMOON_INTERNAL_MODEL_ARTIFACT_STORAGE_BACKEND=s3",
        "HAMOON_GEMMA4_BASE_CHECKPOINT_ROOT",
        "HAMOON_GEMMA4_TRAINING_CONFIG_JSON",
        "HAMOON_GEMMA4_GENERATION_CONFIG_JSON",
    )
    for marker in required:
        assert marker in handoff

    assert "HAMOON_OPENAI_API_KEY" in handoff
    assert "must not be configured" in handoff
    assert "Production Deploy" in handoff
    assert "Production Recovery Verification" in handoff
