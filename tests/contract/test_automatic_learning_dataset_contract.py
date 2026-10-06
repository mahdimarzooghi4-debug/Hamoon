from pathlib import Path


def test_curating_eligible_signal_triggers_automatic_draft_dataset_creation() -> None:
    routes = Path("src/hamoon/domains/learning/api/routes.py").read_text(
        encoding="utf-8"
    )
    handlers = Path(
        "src/hamoon/domains/learning/application/handlers.py"
    ).read_text(encoding="utf-8")

    assert "CreateAutomaticDatasetForCuratedSignalHandler" in routes
    assert "if signal.quality_status is LearningSignalQuality.CURATED" in routes
    assert "AUTO_CURATED_SIGNAL_SELECTION_POLICY_VERSION" in handlers
    assert '"hamoon.auto.diagnosis.learning"' in handlers
    assert '"hamoon.auto.prescription.learning"' in handlers
    assert '"hamoon.auto.outcome.learning"' in handlers
    assert 'version = f"signal-{signal.id}"' in handlers
    assert "DatasetVersionStatus.DRAFT" in handlers


def test_automatic_dataset_creation_does_not_auto_approve_or_promote() -> None:
    handlers = Path(
        "src/hamoon/domains/learning/application/handlers.py"
    ).read_text(encoding="utf-8")

    automatic_block = handlers.split(
        "class CreateAutomaticDatasetForCuratedSignalHandler:",
        maxsplit=1,
    )[1].split("class ApproveDatasetHandler:", maxsplit=1)[0]

    assert ".approve(" not in automatic_block
    assert "promote_routing_policy" not in automatic_block
    assert "DatasetVersionStatus.APPROVED" not in automatic_block
