from pathlib import Path


def test_internal_training_control_plane_is_artifact_bound_and_governed() -> None:
    routes = Path(
        "src/hamoon/domains/intelligence/api/routes.py"
    ).read_text(encoding="utf-8")
    models = Path(
        "src/hamoon/domains/intelligence/infrastructure/models.py"
    ).read_text(encoding="utf-8")
    settings = Path("src/hamoon/app/config/settings.py").read_text(
        encoding="utf-8"
    )
    artifact_store = Path(
        "src/hamoon/infrastructure/ai/artifact_store.py"
    ).read_text(encoding="utf-8")
    frontend = Path(
        "frontend/src/pages/LearningGovernancePage.tsx"
    ).read_text(encoding="utf-8")

    assert '"/api/v1/admin/ai/internal-training-runs"' in routes
    assert "InternalTrainingRunStarted" in routes
    assert "InternalTrainingRunSucceeded" in routes
    assert "InternalTrainingRunFailed" in routes
    assert "INTERNAL_TRAINING_RUN_REQUIRED" in routes
    assert "register_internal_model_candidate(" in routes
    assert "InternalTrainingRunModel" in models
    assert "internal_model_artifact_storage_backend" in settings
    assert "PRODUCTION_INTERNAL_MODEL_ARTIFACT_STORAGE_REQUIRED" in settings
    assert "internal-model-artifacts/sha256/" in artifact_store
    assert "INTERNAL_MODEL_ARTIFACT_DIGEST_MISMATCH" in artifact_store
    assert "Artifact SHA-256" not in frontend
    assert "executeInternalTrainingRun" in frontend


def test_internal_training_does_not_auto_promote_model_or_route() -> None:
    routes = Path(
        "src/hamoon/domains/intelligence/api/routes.py"
    ).read_text(encoding="utf-8")
    start = routes.index("async def execute_internal_training_run(")
    end = routes.index(
        '@router.get(\n    "/api/v1/admin/ai/internal-training-runs"',
        start,
    )
    block = routes[start:end]

    assert "promote_routing_policy" not in block
    assert "RoutingPolicyStatus.ACTIVE" not in block
    assert "AIModelVersionStatus.PRODUCTION" not in block
