from datetime import datetime
from typing import Protocol
from uuid import UUID

from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    DecisionTrace,
    Diagnosis,
    HumanDecision,
    LearningSignal,
)
from hamoon.domains.intelligence.domain.entities import FeaturePackage


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


class LearningSignalRepository(Protocol):
    async def add(self, signal: LearningSignal) -> None: ...
