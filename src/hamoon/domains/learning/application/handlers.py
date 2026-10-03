from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import (
    LearningSignal,
    LearningSignalQuality,
    LearningSignalType,
)
from hamoon.domains.intelligence.domain.registry import EvaluationRunState
from hamoon.domains.intelligence.ports.repositories import (
    AIRuntimeRegistryRepository,
    LearningSignalRepository,
)
from hamoon.domains.intervention.ports.repositories import InterventionRepository
from hamoon.domains.learning.application.commands import (
    ApproveDatasetCommand,
    CreateEvaluationRunCommand,
    CreateOutcomeDatasetCommand,
    CurateLearningSignalCommand,
)
from hamoon.domains.learning.domain.entities import (
    DatasetVersionStatus,
    LearningDatasetItem,
    LearningDatasetVersion,
)
from hamoon.domains.learning.domain.errors import (
    LearningCurationError,
    LearningDatasetError,
)
from hamoon.domains.learning.ports.repositories import LearningDatasetRepository
from hamoon.domains.outcome.ports.repositories import OutcomeRepository
from hamoon.domains.pgor.ports.repositories import PGORSnapshotRepository
from hamoon.domains.provider_result.ports.repositories import ProviderResultRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


_ALLOWED_QUALITY_TRANSITIONS = {
    LearningSignalQuality.RAW: {
        LearningSignalQuality.CURATED,
        LearningSignalQuality.EXCLUDED,
    },
    LearningSignalQuality.CURATED: {LearningSignalQuality.EXCLUDED},
    LearningSignalQuality.EXCLUDED: set(),
}


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class CurateLearningSignalHandler:
    def __init__(
        self,
        *,
        signals: LearningSignalRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._signals = signals
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: CurateLearningSignalCommand,
    ) -> LearningSignal:
        signal = await self._signals.get(command.signal_id)
        if signal is None:
            raise LearningCurationError("LEARNING_SIGNAL_NOT_FOUND")
        if signal.quality_status is not command.expected_quality_status:
            raise LearningCurationError("LEARNING_SIGNAL_QUALITY_CONFLICT")
        if command.to_quality_status not in _ALLOWED_QUALITY_TRANSITIONS[
            signal.quality_status
        ]:
            raise LearningCurationError("LEARNING_SIGNAL_QUALITY_TRANSITION_INVALID")
        if not command.reason_code.strip():
            raise LearningCurationError("CURATION_REASON_REQUIRED")

        now = datetime.now(UTC)
        updated = await self._signals.change_quality(
            signal_id=signal.id,
            expected_quality=signal.quality_status,
            new_quality=command.to_quality_status,
        )
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="LearningSignalQualityChanged",
                event_version=1,
                aggregate_type="LEARNING_SIGNAL",
                aggregate_id=signal.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "learning_signal_id": str(signal.id),
                    "from_quality": signal.quality_status.value,
                    "to_quality": updated.quality_status.value,
                    "reason_code": command.reason_code,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="learning.signal.curate",
                resource_type="LEARNING_SIGNAL",
                resource_id=signal.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_LEARNING_GOVERNANCE",
                metadata={
                    "event_id": str(event_id),
                    "from_quality": signal.quality_status.value,
                    "to_quality": updated.quality_status.value,
                    "reason_code": command.reason_code,
                },
            )
        )
        return updated


class CreateOutcomeDatasetHandler:
    def __init__(
        self,
        *,
        signals: LearningSignalRepository,
        datasets: LearningDatasetRepository,
        outcomes: OutcomeRepository,
        snapshots: PGORSnapshotRepository,
        interventions: InterventionRepository,
        provider_results: ProviderResultRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._signals = signals
        self._datasets = datasets
        self._outcomes = outcomes
        self._snapshots = snapshots
        self._interventions = interventions
        self._provider_results = provider_results
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: CreateOutcomeDatasetCommand,
    ) -> tuple[LearningDatasetVersion, tuple[LearningDatasetItem, ...]]:
        dataset_key = command.dataset_key.strip()
        version = command.version.strip()
        policy_version = command.selection_policy_version.strip()
        if not dataset_key or not version or not policy_version:
            raise LearningDatasetError("DATASET_METADATA_REQUIRED")
        if not command.signal_ids:
            raise LearningDatasetError("DATASET_SIGNALS_REQUIRED")
        if len(set(command.signal_ids)) != len(command.signal_ids):
            raise LearningDatasetError("DUPLICATE_LEARNING_SIGNAL")
        if await self._datasets.get_by_key_version(
            dataset_key=dataset_key,
            version=version,
        ) is not None:
            raise LearningDatasetError("DATASET_VERSION_ALREADY_EXISTS")

        dataset_id = uuid4()
        raw_items: list[dict[str, JsonValue]] = []
        items: list[LearningDatasetItem] = []

        for ordinal, signal_id in enumerate(command.signal_ids, start=1):
            signal = await self._signals.get(signal_id)
            if signal is None:
                raise LearningDatasetError("LEARNING_SIGNAL_NOT_FOUND")
            if signal.quality_status is not LearningSignalQuality.CURATED:
                raise LearningDatasetError("LEARNING_SIGNAL_NOT_CURATED")
            if signal.signal_type is not LearningSignalType.OUTCOME_OBSERVED:
                raise LearningDatasetError("OUTCOME_SIGNAL_REQUIRED")
            if signal.outcome_id is None:
                raise LearningDatasetError("OUTCOME_REFERENCE_REQUIRED")

            outcome = await self._outcomes.get(signal.outcome_id)
            if outcome is None or outcome.classification is None:
                raise LearningDatasetError("REVIEWED_OUTCOME_REQUIRED")
            pre = await self._snapshots.get(outcome.pre_pgor_snapshot_id)
            post = await self._snapshots.get(outcome.post_pgor_snapshot_id)
            intervention = await self._interventions.get(outcome.intervention_id)
            if pre is None or post is None or intervention is None:
                raise LearningDatasetError("OUTCOME_PROVENANCE_INCOMPLETE")

            provider_result_type: str | None = None
            provider_result_status: str | None = None
            if outcome.provider_result_id is not None:
                provider_result = await self._provider_results.get(
                    outcome.provider_result_id
                )
                if provider_result is None:
                    raise LearningDatasetError("PROVIDER_RESULT_NOT_FOUND")
                provider_result_type = provider_result.result_type
                provider_result_status = provider_result.result_status

            input_payload: dict[str, JsonValue] = {
                "schema_version": "outcome-learning-input-v1",
                "pre_pgor": {
                    "p": str(pre.p),
                    "g": str(pre.g),
                    "o": str(pre.o),
                    "r": str(pre.r),
                    "e": str(pre.e),
                },
                "post_pgor": {
                    "p": str(post.p),
                    "g": str(post.g),
                    "o": str(post.o),
                    "r": str(post.r),
                    "e": str(post.e),
                },
                "delta": {
                    "p": str(outcome.p_delta),
                    "g": str(outcome.g_delta),
                    "o": str(outcome.o_delta),
                    "r": str(outcome.r_delta),
                    "e": str(outcome.e_delta),
                },
                "intervention_type": intervention.intervention_type.value,
                "target_pgor_variable": intervention.target_pgor_variable.value,
                "provider_result_type": provider_result_type,
                "provider_result_status": provider_result_status,
                "methodology_version": outcome.methodology_version,
                "causal_claim_allowed": False,
            }
            target_payload: dict[str, JsonValue] = {
                "classification": outcome.classification.value,
                "human_review_required": True,
            }
            source_refs = (
                f"learning_signal:{signal.id}",
                f"outcome:{outcome.id}",
                f"pgor_snapshot:{pre.id}",
                f"pgor_snapshot:{post.id}",
                f"intervention:{intervention.id}",
            )
            raw_item: dict[str, JsonValue] = {
                "learning_signal_id": str(signal.id),
                "signal_type": signal.signal_type.value,
                "signal_label": signal.signal_label,
                "input": input_payload,
                "target": target_payload,
                "source_refs": list(source_refs),
            }
            raw_items.append(raw_item)
            items.append(
                LearningDatasetItem(
                    id=uuid4(),
                    dataset_version_id=dataset_id,
                    ordinal=ordinal,
                    learning_signal_id=signal.id,
                    signal_type=signal.signal_type,
                    signal_label=signal.signal_label,
                    input_payload=input_payload,
                    target_payload=target_payload,
                    source_refs=source_refs,
                )
            )

        manifest_digest = _json_digest(
            {
                "dataset_key": dataset_key,
                "version": version,
                "selection_policy_version": policy_version,
                "items": raw_items,
            }
        )
        now = datetime.now(UTC)
        dataset = LearningDatasetVersion(
            id=dataset_id,
            dataset_key=dataset_key,
            version=version,
            purpose="OUTCOME_INTERPRETATION",
            selection_policy_version=policy_version,
            status=DatasetVersionStatus.DRAFT,
            manifest_ref=f"db://learning-datasets/{dataset_id}/items",
            manifest_digest=manifest_digest,
            created_at=now,
            created_by=command.actor_id,
        )
        await self._datasets.add(dataset, tuple(items))

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="DatasetVersionCreated",
                event_version=1,
                aggregate_type="LEARNING_DATASET",
                aggregate_id=dataset.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "dataset_id": str(dataset.id),
                    "dataset_key": dataset.dataset_key,
                    "version": dataset.version,
                    "purpose": dataset.purpose,
                    "selection_policy_version": dataset.selection_policy_version,
                    "item_count": len(items),
                    "manifest_digest": dataset.manifest_digest,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="learning.dataset.create",
                resource_type="LEARNING_DATASET",
                resource_id=dataset.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_EVALUATION_DATASET",
                metadata={
                    "event_id": str(event_id),
                    "item_count": len(items),
                    "manifest_digest": dataset.manifest_digest,
                    "selection_policy_version": dataset.selection_policy_version,
                },
            )
        )
        return dataset, tuple(items)


class ApproveDatasetHandler:
    def __init__(
        self,
        *,
        datasets: LearningDatasetRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._datasets = datasets
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: ApproveDatasetCommand,
    ) -> LearningDatasetVersion:
        dataset = await self._datasets.get(command.dataset_id)
        if dataset is None:
            raise LearningDatasetError("LEARNING_DATASET_NOT_FOUND")
        now = datetime.now(UTC)
        try:
            approved = dataset.approve(
                approved_at=now,
                approved_by=command.actor_id,
            )
        except ValueError as exc:
            raise LearningDatasetError(str(exc)) from exc
        await self._datasets.approve(approved)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="DatasetVersionApproved",
                event_version=1,
                aggregate_type="LEARNING_DATASET",
                aggregate_id=dataset.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "dataset_id": str(dataset.id),
                    "dataset_key": dataset.dataset_key,
                    "version": dataset.version,
                    "manifest_digest": dataset.manifest_digest,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="learning.dataset.approve",
                resource_type="LEARNING_DATASET",
                resource_id=dataset.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_EVALUATION_DATASET",
                metadata={
                    "event_id": str(event_id),
                    "manifest_digest": dataset.manifest_digest,
                },
            )
        )
        return approved


class CreateEvaluationRunHandler:
    def __init__(
        self,
        *,
        datasets: LearningDatasetRepository,
        registry: AIRuntimeRegistryRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._datasets = datasets
        self._registry = registry
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: CreateEvaluationRunCommand,
    ) -> EvaluationRunState:
        dataset = await self._datasets.get(command.dataset_version_id)
        if dataset is None:
            raise LearningDatasetError("LEARNING_DATASET_NOT_FOUND")
        if dataset.status is not DatasetVersionStatus.APPROVED:
            raise LearningDatasetError("LEARNING_DATASET_NOT_APPROVED")
        if dataset.purpose != command.task_class.value:
            raise LearningDatasetError("EVALUATION_DATASET_PURPOSE_MISMATCH")
        if not command.evaluation_policy_version.strip():
            raise LearningDatasetError("EVALUATION_POLICY_VERSION_REQUIRED")

        now = datetime.now(UTC)
        evaluation = await self._registry.create_evaluation_run(
            task_class=command.task_class,
            model_version_id=command.model_version_id,
            prompt_policy_version_id=command.prompt_policy_version_id,
            dataset_version_id=dataset.id,
            evaluation_policy_version=command.evaluation_policy_version.strip(),
            started_at=now,
        )
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="EvaluationRunStarted",
                event_version=1,
                aggregate_type="EVALUATION_RUN",
                aggregate_id=evaluation.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "evaluation_run_id": str(evaluation.id),
                    "task_class": command.task_class.value,
                    "dataset_version_id": str(dataset.id),
                    "model_version_id": str(command.model_version_id),
                    "prompt_policy_version_id": str(command.prompt_policy_version_id),
                    "evaluation_policy_version": command.evaluation_policy_version,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="ai.evaluation.start",
                resource_type="EVALUATION_RUN",
                resource_id=evaluation.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_MODEL_GOVERNANCE",
                metadata={
                    "event_id": str(event_id),
                    "dataset_version_id": str(dataset.id),
                    "manifest_digest": dataset.manifest_digest,
                },
            )
        )
        return evaluation
