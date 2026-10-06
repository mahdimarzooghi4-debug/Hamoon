from pathlib import Path


def test_production_internal_model_contract_has_no_ai_api_dependency() -> None:
    factory = Path(
        "src/hamoon/infrastructure/ai/production_factory.py"
    ).read_text(encoding="utf-8")
    contracts = Path(
        "src/hamoon/infrastructure/ai/contracts.py"
    ).read_text(encoding="utf-8")
    registry = Path(
        "src/hamoon/domains/intelligence/domain/registry.py"
    ).read_text(encoding="utf-8")
    settings = Path("src/hamoon/app/config/settings.py").read_text(
        encoding="utf-8"
    )

    assert 'INTERNAL_MODEL_PROVIDER_CODE = "INTERNAL_MODEL"' in registry
    assert "INTERNAL_MODEL_PROVIDER_CODE" in factory
    assert "INTERNAL_MODEL_RUNTIME_NOT_CONFIGURED" in factory
    assert "INTERNAL_MODEL_EXECUTOR_NOT_REGISTERED" in factory
    assert "InternalModelExecutionMode.IN_PROCESS" in factory
    assert 'IN_PROCESS = "IN_PROCESS"' in contracts
    assert "InternalModelArtifactContract" in contracts
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
        assert forbidden not in contracts


def test_internal_training_and_execution_core_is_in_process_and_model_agnostic() -> None:
    runtime_path = Path("src/hamoon/infrastructure/ai/internal_model.py")
    assert runtime_path.exists()
    runtime = runtime_path.read_text(encoding="utf-8")

    for required in (
        "class InternalModelArtifactStore(Protocol):",
        "class InternalModelTrainer(Protocol):",
        "class InternalModelExecutor(Protocol):",
        "class InternalTrainingEngine:",
        "class InternalModelProviderAdapter:",
        "configure_internal_model_runtime",
    ):
        assert required in runtime

    for forbidden in (
        "httpx",
        "requests",
        "OpenAI",
        "vllm",
        "tgi",
        "Llama",
        "Qwen",
        "Mistral",
    ):
        assert forbidden not in runtime

    for obsolete_path in (
        "src/hamoon/infrastructure/ai/native_model.py",
        "src/hamoon/infrastructure/ai/training.py",
        "src/hamoon/infrastructure/ai/providers/native.py",
        "src/hamoon/evaluation/diagnosis_candidate.py",
        "src/hamoon/evaluation/outcome_candidate.py",
    ):
        assert not Path(obsolete_path).exists()


def test_model_registry_requires_versioned_training_and_evaluation_lineage() -> None:
    models = Path(
        "src/hamoon/domains/intelligence/infrastructure/models.py"
    ).read_text(encoding="utf-8")
    repository = Path(
        "src/hamoon/domains/intelligence/infrastructure/repositories.py"
    ).read_text(encoding="utf-8")

    assert "artifact_sha256" in models
    assert "training_dataset_version_id" in models
    assert "training_dataset_manifest_digest" in models
    assert "training_pipeline_version" in models
    assert "production_evaluation_run_id" in models

    assert "model_version.production_evaluation_run_id = evaluation.id" in repository
    assert (
        "AIModelVersionModel.production_evaluation_run_id" in repository
        and "== EvaluationRunModel.id" in repository
    )
    assert "MODEL_ARTIFACT_DIGEST_REQUIRED" in repository
    assert "MODEL_TRAINING_LINEAGE_REQUIRED" in repository
    assert "EVALUATION_DATASET_LINEAGE_MISMATCH" not in repository
    assert "training_dataset_version_id" in repository
    assert "training_dataset_manifest_digest" in repository
    assert "dataset_version_id" in repository
    assert "dataset_manifest_digest" in repository
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


def test_api_based_self_hosted_runtime_cannot_reenter_production_surface() -> None:
    forbidden_markers = (
        "sovereign_ai_endpoint",
        "sovereign_ai_token",
        "SelfHostedAIProvider",
        "providers.self_hosted",
        "SELF_HOSTED",
    )
    production_paths = (
        "src/hamoon/infrastructure/ai/production_factory.py",
        "src/hamoon/infrastructure/ai/outcome_factory.py",
        "src/hamoon/domains/intelligence/api/routes.py",
        "src/hamoon/domains/prescription/api/routes.py",
        "src/hamoon/domains/outcome/api/intelligence_routes.py",
    )

    for path in production_paths:
        source = Path(path).read_text(encoding="utf-8")
        for marker in forbidden_markers:
            assert marker not in source

    for obsolete_path in (
        "src/hamoon/infrastructure/ai/providers/self_hosted.py",
        ".github/workflows/sovereign-ai-integration.yml",
        "scripts/execute_sovereign_ai_verification.py",
        "scripts/verify_sovereign_ai_integration.py",
    ):
        assert not Path(obsolete_path).exists()


def test_concrete_gemma4_runtime_is_pinned_local_only_and_qwen_is_retired() -> None:
    baseline = Path(
        "src/hamoon/infrastructure/ai/gemma4_baseline.py"
    ).read_text(encoding="utf-8")
    runtime = Path(
        "src/hamoon/infrastructure/ai/gemma4_runtime.py"
    ).read_text(encoding="utf-8")
    main = Path("src/hamoon/app/main.py").read_text(encoding="utf-8")
    requirements = Path(
        "requirements/internal-ai-gemma4.txt"
    ).read_text(encoding="utf-8")

    assert 'GEMMA4_BASELINE_MODEL_ID: Final = "google/gemma-4-12B-it"' in baseline
    assert (
        "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"
        in baseline
    )
    assert (
        "5a84cb313260ac447237b890387116dfa8682e49a6b44bc585ae8353abbff18d"
        in baseline
    )
    assert "local_files_only=True" in runtime
    assert "AutoModelForMultimodalLM.from_pretrained" in runtime
    assert "PeftModel.from_pretrained" in runtime
    assert "GEMMA4_TRAINING_CONFIGURATION_REQUIRED" in runtime
    assert "GEMMA4_GENERATION_CONFIGURATION_REQUIRED" in runtime
    assert "Gemma4LoRATrainer" in main
    assert "Gemma4LoRAExecutor" in main
    assert "transformers==5.18.0" in requirements
    assert "peft==0.21.2" in requirements
    assert "torch==2.14.1" in requirements

    assert not Path(
        "src/hamoon/infrastructure/ai/qwen3_baseline.py"
    ).exists()
    assert not Path(
        "tests/unit/ai/test_qwen3_baseline_contract.py"
    ).exists()
