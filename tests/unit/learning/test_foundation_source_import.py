from dataclasses import replace
from uuid import UUID

import pytest

from hamoon.domains.learning.application.commands import (
    ApproveDatasetCommand,
    ImportApprovedFoundationDatasetCommand,
)
from hamoon.domains.learning.application.foundation_source import (
    FOUNDATION_SOURCE_SELECTION_POLICY_VERSION,
    FoundationSourceLoader,
)
from hamoon.domains.learning.application.handlers import (
    ApproveDatasetHandler,
    ImportApprovedFoundationDatasetHandler,
)
from hamoon.domains.learning.domain.entities import (
    DatasetSourceKind,
    DatasetVersionStatus,
)
from hamoon.domains.learning.domain.errors import LearningDatasetError
from hamoon.infrastructure.ai.contracts import AITaskClass

ACTOR = UUID("11111111-1111-1111-1111-111111111111")


class Datasets:
    def __init__(self) -> None:
        self.dataset = None
        self.items = ()

    async def get_by_key_version(self, *, dataset_key, version):
        if (
            self.dataset is not None
            and self.dataset.dataset_key == dataset_key
            and self.dataset.version == version
        ):
            return self.dataset
        return None

    async def add(self, dataset, items):
        self.dataset = dataset
        self.items = items

    async def get(self, dataset_id):
        if self.dataset is not None and self.dataset.id == dataset_id:
            return self.dataset
        return None

    async def list_items(self, dataset_id):
        if self.dataset is not None and self.dataset.id == dataset_id:
            return list(self.items)
        return []

    async def approve(self, dataset):
        self.dataset = dataset


class Signals:
    async def get(self, _signal_id):
        raise AssertionError("foundation approval must not read LearningSignal")


class Recorder:
    def __init__(self) -> None:
        self.items = []

    async def record(self, item):
        self.items.append(item)


def _command(task_class: AITaskClass) -> ImportApprovedFoundationDatasetCommand:
    return ImportApprovedFoundationDatasetCommand(
        task_class=task_class,
        source_version="v1",
        actor_id=ACTOR,
        request_id="req-foundation",
        correlation_id="corr-foundation",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_class", "expected_count"),
    [
        (AITaskClass.DIAGNOSIS, 12),
        (AITaskClass.OUTCOME_INTERPRETATION, 12),
    ],
)
async def test_approved_foundation_source_imports_as_draft_without_fake_signals(
    task_class: AITaskClass,
    expected_count: int,
) -> None:
    datasets = Datasets()
    events = Recorder()
    audits = Recorder()
    handler = ImportApprovedFoundationDatasetHandler(
        datasets=datasets,
        source_loader=FoundationSourceLoader(),
        events=events,
        audits=audits,
    )

    dataset, items = await handler.handle(_command(task_class))

    assert dataset.status is DatasetVersionStatus.DRAFT
    assert (
        dataset.source_kind
        is DatasetSourceKind.APPROVED_FOUNDATION_SOURCE
    )
    assert (
        dataset.selection_policy_version
        == FOUNDATION_SOURCE_SELECTION_POLICY_VERSION
    )
    assert dataset.source_ref is not None
    assert dataset.source_digest is not None
    assert len(dataset.source_digest) == 64
    assert dataset.source_approval_ref is not None
    assert len(items) == expected_count
    assert all(item.learning_signal_id is None for item in items)
    assert all(item.signal_type is None for item in items)
    assert all(item.signal_label is None for item in items)
    assert all(item.source_key for item in items)
    assert len({item.source_key for item in items}) == expected_count
    assert events.items
    assert audits.items


@pytest.mark.asyncio
async def test_foundation_import_is_idempotent_for_same_attested_source() -> None:
    datasets = Datasets()
    handler = ImportApprovedFoundationDatasetHandler(
        datasets=datasets,
        source_loader=FoundationSourceLoader(),
        events=Recorder(),
        audits=Recorder(),
    )

    first_dataset, first_items = await handler.handle(
        _command(AITaskClass.DIAGNOSIS)
    )
    second_dataset, second_items = await handler.handle(
        _command(AITaskClass.DIAGNOSIS)
    )

    assert second_dataset.id == first_dataset.id
    assert second_items == first_items


@pytest.mark.asyncio
async def test_foundation_runtime_approval_reattests_source_without_signals() -> None:
    datasets = Datasets()
    loader = FoundationSourceLoader()
    dataset, _items = await ImportApprovedFoundationDatasetHandler(
        datasets=datasets,
        source_loader=loader,
        events=Recorder(),
        audits=Recorder(),
    ).handle(_command(AITaskClass.OUTCOME_INTERPRETATION))

    approved = await ApproveDatasetHandler(
        datasets=datasets,
        signals=Signals(),
        events=Recorder(),
        audits=Recorder(),
        foundation_sources=loader,
    ).handle(
        ApproveDatasetCommand(
            dataset_id=dataset.id,
            actor_id=ACTOR,
            request_id="req-approve",
            correlation_id="corr-approve",
        )
    )

    assert approved.status is DatasetVersionStatus.APPROVED
    assert approved.approved_by == ACTOR


@pytest.mark.asyncio
async def test_foundation_approval_fails_if_imported_item_drifted() -> None:
    datasets = Datasets()
    loader = FoundationSourceLoader()
    dataset, items = await ImportApprovedFoundationDatasetHandler(
        datasets=datasets,
        source_loader=loader,
        events=Recorder(),
        audits=Recorder(),
    ).handle(_command(AITaskClass.DIAGNOSIS))

    datasets.items = (
        replace(
            items[0],
            target_payload={"schema_version": "tampered"},
        ),
        *items[1:],
    )

    with pytest.raises(
        LearningDatasetError,
        match="FOUNDATION_SOURCE_ATTESTATION_MISMATCH",
    ):
        await ApproveDatasetHandler(
            datasets=datasets,
            signals=Signals(),
            events=Recorder(),
            audits=Recorder(),
            foundation_sources=loader,
        ).handle(
            ApproveDatasetCommand(
                dataset_id=dataset.id,
                actor_id=ACTOR,
                request_id="req-tampered",
                correlation_id="corr-tampered",
            )
        )

    assert datasets.dataset is not None
    assert datasets.dataset.status is DatasetVersionStatus.DRAFT
