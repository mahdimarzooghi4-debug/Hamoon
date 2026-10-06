from pathlib import Path


def test_production_internal_model_contract_has_no_ai_api_dependency() -> None:
    factory = Path(
        "src/hamoon/infrastructure/ai/production_factory.py"
    ).read_text(encoding="utf-8")
    registry = Path(
        "src/hamoon/domains/intelligence/domain/registry.py"
    ).read_text(encoding="utf-8")
    settings = Path("src/hamoon/app/config/settings.py").read_text(
        encoding="utf-8"
    )

    assert 'INTERNAL_MODEL_PROVIDER_CODE = "INTERNAL_MODEL"' in registry
    assert "INTERNAL_MODEL_PROVIDER_CODE" in factory
    assert "INTERNAL_MODEL_EXECUTOR_NOT_IMPLEMENTED" in factory
    assert "providers.native" not in factory

    for forbidden in (
        "sovereign_ai_endpoint",
        "sovereign_ai_token",
        "SelfHostedAIProvider",
        "SELF_HOSTED",
        "OpenAIProvider",
        "vllm",
        "tgi",
    ):
        assert forbidden not in factory
        assert forbidden not in settings


def test_unapproved_training_and_execution_engine_is_absent() -> None:
    for path in (
        "src/hamoon/infrastructure/ai/native_model.py",
        "src/hamoon/infrastructure/ai/training.py",
        "src/hamoon/infrastructure/ai/providers/native.py",
        "src/hamoon/evaluation/diagnosis_candidate.py",
        "src/hamoon/evaluation/outcome_candidate.py",
    ):
        assert not Path(path).exists()


def test_model_registry_requires_versioned_training_and_evaluation_lineage() -> None:
    models = Path(
        "src/hamoon/domains/intelligence/infrastructure/models.py"
    ).read_text(encoding="utf-8")
    repository = Path(
        "src/hamoon/domains/intelligence/infrastructure/repositories.py"
    ).read_text(encoding="utf-8")

    assert "artifact_sha256" in models
    assert "training_dataset_manifest_digest" in models
    assert "training_pipeline_version" in models

    assert "MODEL_ARTIFACT_DIGEST_REQUIRED" in repository
    assert "MODEL_TRAINING_LINEAGE_REQUIRED" in repository
    assert "EVALUATION_ATTESTATION_REQUIRED" in repository
    assert "EvaluationStatus.PASSED" in repository
    assert "RoutingPolicyStatus.DRAFT" in repository
    assert "EXTERNAL_AI_PROVIDER_PRODUCTION_FORBIDDEN" in repository


def test_runtime_unavailability_creates_human_fallback_work_items() -> None:
    for path in (
        "src/hamoon/domains/intelligence/api/routes.py",
        "src/hamoon/domains/prescription/api/routes.py",
        "src/hamoon/domains/outcome/api/intelligence_routes.py",
    ):
        source = Path(path).read_text(encoding="utf-8")
        assert "EnsureWorkItemHandler" in source
        assert "WorkItemType.AI_FALLBACK" in source
        assert "HTTP_503_SERVICE_UNAVAILABLE" in source
