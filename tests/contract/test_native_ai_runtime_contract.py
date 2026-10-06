from pathlib import Path


def test_production_ai_runtime_has_no_network_provider_dependency() -> None:
    native_provider = Path(
        "src/hamoon/infrastructure/ai/providers/native.py"
    ).read_text(encoding="utf-8")
    production_factory = Path(
        "src/hamoon/infrastructure/ai/production_factory.py"
    ).read_text(encoding="utf-8")
    settings = Path("src/hamoon/app/config/settings.py").read_text(
        encoding="utf-8"
    )

    for forbidden in ("httpx", "requests", "aiohttp", "socket", "grpc"):
        assert forbidden not in native_provider

    assert 'code = "HAMOON_NATIVE"' in native_provider
    assert "HAMOON_NATIVE_PROVIDER_CODE" in production_factory
    assert "EXTERNAL_AI_PROVIDER_PRODUCTION_FORBIDDEN" in production_factory
    assert "PRODUCTION_EXTERNAL_AI_CREDENTIAL_FORBIDDEN" in settings
    assert "ai_model_root" in settings


def test_external_ai_adapter_is_not_part_of_current_runtime() -> None:
    assert not Path(
        "src/hamoon/infrastructure/ai/providers/openai.py"
    ).exists()


def test_native_ai_growth_keeps_human_governance_boundary() -> None:
    training = Path("src/hamoon/infrastructure/ai/training.py").read_text(
        encoding="utf-8"
    )
    repository = Path(
        "src/hamoon/domains/intelligence/infrastructure/repositories.py"
    ).read_text(encoding="utf-8")

    assert "TRAINING_DATASET_NOT_APPROVED" in training
    assert "AIModelVersionStatus.CANDIDATE" in repository
    assert "EvaluationStatus.PASSED" in repository
    assert "RoutingPolicyStatus.DRAFT" in repository
    assert "EXTERNAL_AI_PROVIDER_PRODUCTION_FORBIDDEN" in repository
    assert "MODEL_ARTIFACT_DIGEST_REQUIRED" in repository



def test_candidate_evaluators_are_native_and_api_free() -> None:
    for path in (
        "src/hamoon/evaluation/diagnosis_candidate.py",
        "src/hamoon/evaluation/outcome_candidate.py",
    ):
        source = Path(path).read_text(encoding="utf-8")
        assert "HamoonNativeAIProvider" in source
        for forbidden in (
            "OpenAIProvider",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "api.openai.com",
        ):
            assert forbidden not in source
