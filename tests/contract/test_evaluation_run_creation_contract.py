from pathlib import Path


def test_evaluation_run_creation_is_dataset_bound_and_governed() -> None:
    routes = Path(
        "src/hamoon/domains/intelligence/api/routes.py"
    ).read_text(encoding="utf-8")
    schemas = Path(
        "src/hamoon/domains/intelligence/api/schemas.py"
    ).read_text(encoding="utf-8")
    repository = Path(
        "src/hamoon/domains/intelligence/infrastructure/repositories.py"
    ).read_text(encoding="utf-8")

    assert '"/api/v1/admin/ai/evaluations"' in routes
    assert "async def create_ai_evaluation(" in routes
    assert "CreateAIEvaluationRunRequest" in schemas
    assert "EVALUATION_DATASET_NOT_APPROVED" in routes
    assert "EVALUATION_DATASET_PURPOSE_MISMATCH" in routes
    assert "EVALUATION_DATASET_EMPTY" in routes
    assert "dataset_manifest_digest=dataset.manifest_digest" in routes
    assert "EvaluationRunCreated" in routes
    assert 'action="ai.evaluation.create"' in routes

    creation_start = routes.index("async def create_ai_evaluation(")
    completion_start = routes.index("async def complete_ai_evaluation(")
    creation_block = routes[creation_start:completion_start]
    assert "promote_routing_policy" not in creation_block
    assert "AIModelVersionStatus.PRODUCTION" not in creation_block

    assert "EVALUATION_REQUIRES_INTERNAL_MODEL" in repository
    assert "EVALUATION_MODEL_PURPOSE_MISMATCH" in repository
    assert "EVALUATION_MODEL_ARTIFACT_REQUIRED" in repository
    assert "EVALUATION_MODEL_TRAINING_LINEAGE_REQUIRED" in repository
    assert "model_version.training_dataset_version_id is None" in repository
    assert "require_independent_evaluation_dataset(" in repository
    assert "EVALUATION_MODEL_VERSION_NOT_ELIGIBLE" in repository
    assert "EVALUATION_PROMPT_NOT_ACTIVE" in repository
    assert "EVALUATION_PROMPT_PURPOSE_MISMATCH" in repository


def test_evaluation_run_creation_requires_explicit_policy_version() -> None:
    schemas = Path(
        "src/hamoon/domains/intelligence/api/schemas.py"
    ).read_text(encoding="utf-8")

    request_start = schemas.index("class CreateAIEvaluationRunRequest")
    request_end = schemas.index("class CompleteAIEvaluationRequest")
    request_block = schemas[request_start:request_end]

    assert "task_class: AITaskClass" in request_block
    assert "model_version_id: UUID" in request_block
    assert "prompt_policy_version_id: UUID" in request_block
    assert "dataset_version_id: UUID" in request_block
    assert "evaluation_policy_version: str = Field(" in request_block
    assert "default=" not in request_block


def test_evaluation_completion_revalidates_dataset_and_report_binding() -> None:
    routes = Path(
        "src/hamoon/domains/intelligence/api/routes.py"
    ).read_text(encoding="utf-8")
    governance = Path(
        "src/hamoon/domains/intelligence/application/evaluation_governance.py"
    ).read_text(encoding="utf-8")

    completion_start = routes.index("async def complete_ai_evaluation(")
    completion_end = routes.index('@router.post(\n    "/api/v1/admin/ai/routing-policies"', completion_start)
    completion_block = routes[completion_start:completion_end]

    assert "EVALUATION_DATASET_NOT_APPROVED" in completion_block
    assert "EVALUATION_DATASET_PURPOSE_MISMATCH" in completion_block
    assert "EVALUATION_DATASET_DIGEST_CHANGED" in completion_block
    assert "EVALUATION_DATASET_DIGEST_MISMATCH" in completion_block
    assert "EVALUATION_DATASET_EMPTY" in completion_block
    assert "expected_dataset_version=dataset.version" in completion_block
    assert "EVALUATION_REPORT_DATASET_MISMATCH" in governance

