from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    DecisionTrace,
    Diagnosis,
    HumanDecision,
    LearningSignal,
)
from hamoon.domains.intelligence.domain.entities import FeaturePackage
from hamoon.domains.intelligence.domain.registry import (
    EvaluationRunState,
    ResolvedAIRoute,
    RoutingPromotionResult,
)
from hamoon.infrastructure.ai.contracts import AITaskClass


class FeaturePackageRepository(Protocol):
    async def add(self, package: FeaturePackage) -> None: ...

    async def get(self, package_id: UUID) -> FeaturePackage | None: ...

    async def get_by_snapshot(
        self,
        *,
        snapshot_id: UUID,
        schema_version: str,
    ) -> FeaturePackage | None: ...


class AIDecisionRepository(Protocol):
    async def add(self, decision: AIDecision) -> None: ...

    async def get(self, decision_id: UUID) -> AIDecision | None: ...


class DiagnosisRepository(Protocol):
    async def add(self, diagnosis: Diagnosis) -> None: ...

    async def get(self, diagnosis_id: UUID) -> Diagnosis | None: ...

    async def update(
        self,
        diagnosis: Diagnosis,
        *,
        expected_version: int,
    ) -> None: ...


class HumanDecisionRepository(Protocol):
    async def add(self, decision: HumanDecision) -> None: ...

    async def get(self, decision_id: UUID) -> HumanDecision | None: ...


class DecisionTraceRepository(Protocol):
    async def add(self, trace: DecisionTrace) -> None: ...

    async def get_by_ai_decision(
        self,
        ai_decision_id: UUID,
    ) -> DecisionTrace | None: ...

    async def attach_human_decision(
        self,
        *,
        ai_decision_id: UUID,
        human_decision_id: UUID,
        closed_at: datetime | None,
    ) -> None: ...

    async def attach_intervention(
        self,
        *,
        ai_decision_id: UUID,
        intervention_id: UUID,
    ) -> None: ...


class LearningSignalRepository(Protocol):
    async def add(self, signal: LearningSignal) -> None: ...

    async def get(self, signal_id: UUID) -> LearningSignal | None: ...

    async def list(
        self,
        *,
        quality_status: object | None,
        signal_type: object | None,
        limit: int,
    ) -> list[LearningSignal]: ...

    async def change_quality(
        self,
        *,
        signal_id: UUID,
        expected_quality: object,
        new_quality: object,
    ) -> LearningSignal: ...


class AIRuntimeRegistryRepository(Protocol):
    async def resolve_active_route(
        self,
        task_class: AITaskClass,
    ) -> ResolvedAIRoute | None: ...

    async def get_evaluation_run(
        self,
        evaluation_run_id: UUID,
    ) -> EvaluationRunState | None: ...

    async def create_evaluation_run(
        self,
        *,
        task_class: AITaskClass,
        model_version_id: UUID,
        prompt_policy_version_id: UUID,
        dataset_version_id: UUID,
        evaluation_policy_version: str,
        started_at: datetime,
    ) -> EvaluationRunState: ...

    async def complete_evaluation_run(
        self,
        *,
        evaluation_run_id: UUID,
        passed: bool,
        summary_metrics: dict[str, JsonValue],
        completed_at: datetime,
    ) -> EvaluationRunState: ...

    async def promote_routing_policy(
        self,
        *,
        routing_policy_id: UUID,
        activated_at: datetime,
    ) -> RoutingPromotionResult: ...
