from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from hamoon.domains.assessment.application.commands import (
    ChangeObservationValidationCommand,
    RecordIndicatorObservationCommand,
    ResolveAcceptedObservationCommand,
    StartAssessmentCommand,
)
from hamoon.domains.assessment.application.handlers import (
    ChangeObservationValidationHandler,
    RecordIndicatorObservationHandler,
    ResolveAcceptedObservationHandler,
    StartAssessmentHandler,
)
from hamoon.domains.assessment.domain.entities import (
    AcceptedIndicatorObservation,
    Assessment,
    AssessmentType,
    IndicatorObservation,
    ObservationValidationState,
    ObservationValidationStatus,
)
from hamoon.domains.family_data.application.commands import (
    ChangeFactValidationCommand,
    RecordHouseholdFactCommand,
    ResolveAcceptedFactCommand,
)
from hamoon.domains.family_data.application.handlers import (
    ChangeFactValidationHandler,
    RecordHouseholdFactHandler,
    ResolveAcceptedFactHandler,
)
from hamoon.domains.family_data.domain.entities import (
    CurrentAcceptedFact,
    DataSource,
    FactValidationState,
    FactValidationStatus,
    FactValueType,
    HouseholdFact,
    SourceType,
)
from hamoon.domains.household.application.commands import CreateHouseholdCommand
from hamoon.domains.household.application.handlers import CreateHouseholdHandler
from hamoon.domains.household.domain.entities import CaseAssignment, Household
from hamoon.domains.intelligence.application.diagnosis_commands import (
    GenerateDiagnosisCommand,
    ReviewDiagnosisCommand,
)
from hamoon.domains.intelligence.application.diagnosis_handlers import (
    GenerateDiagnosisHandler,
    ReviewDiagnosisHandler,
)
from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIExecutionResult,
    DecisionTrace,
    Diagnosis,
    HumanDecision,
    HumanDecisionAction,
    LearningSignal,
)
from hamoon.domains.intelligence.domain.entities import FeaturePackage
from hamoon.domains.intervention.application.commands import ActivateInterventionCommand
from hamoon.domains.intervention.application.handlers import ActivateInterventionHandler
from hamoon.domains.intervention.domain.entities import Intervention, InterventionType
from hamoon.domains.operations.application.handlers import (
    MarkPostPGORReadyHandler,
    MaterializeReassessmentWorkItemHandler,
    StartPlannedReassessmentHandler,
)
from hamoon.domains.operations.domain.entities import ReassessmentPlan, WorkItem
from hamoon.domains.outcome.application.commands import (
    PrepareOutcomeCommand,
    ReviewOutcomeCommand,
)
from hamoon.domains.outcome.application.handlers import (
    PrepareOutcomeHandler,
    ReviewOutcomeHandler,
)
from hamoon.domains.outcome.domain.entities import (
    HamoonOutcome,
    OutcomeClassification,
    OutcomeStatus,
)
from hamoon.domains.pgor.application.commands import CalculateOfficialPGORCommand
from hamoon.domains.pgor.application.handlers import CalculateOfficialPGORHandler
from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionBundle,
    PGORDefinitionStatus,
    PGORDefinitionVersion,
    PGORDimensionDefinition,
    PGORIndicatorDefinition,
    PGORVariableCode,
    PGORVariableDefinition,
    RequirementPolicyStatus,
)
from hamoon.domains.pgor.domain.engine import FormulaStatus, FormulaVersion
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot, PGORSnapshotInput
from hamoon.domains.prescription.application.commands import (
    GeneratePrescriptionCommand,
    ReviewPrescriptionCommand,
)
from hamoon.domains.prescription.application.handlers import GeneratePrescriptionHandler
from hamoon.domains.prescription.application.review import ReviewPrescriptionHandler
from hamoon.domains.prescription.domain.entities import (
    Prescription,
    PrescriptionItem,
    PrescriptionItemStatus,
)
from hamoon.domains.provider.application.commands import MatchProvidersCommand
from hamoon.domains.provider.application.matching import MatchProvidersHandler
from hamoon.domains.provider.domain.entities import (
    CapacityStatus,
    EligibilityOperator,
    Provider,
    ProviderCapacitySnapshot,
    ProviderEligibilityRule,
    ProviderMatch,
    ProviderSelection,
    ProviderService,
    ProviderStatus,
)
from hamoon.domains.provider_result.application.commands import (
    SubmitProviderResultCommand,
)
from hamoon.domains.provider_result.application.handlers import (
    SubmitProviderResultHandler,
)
from hamoon.domains.provider_result.domain.entities import ProviderResult
from hamoon.domains.referral.application.commands import (
    CreateReferralCommand,
    SendReferralCommand,
    SharedFactInput,
)
from hamoon.domains.referral.application.handlers import CreateReferralHandler
from hamoon.domains.referral.application.lifecycle import SendReferralHandler
from hamoon.domains.referral.domain.entities import (
    Referral,
    ReferralDispatch,
    ReferralEvent,
)
from hamoon.infrastructure.ai.diagnosis_runtime import DIAGNOSIS_V1_SCHEMA
from hamoon.infrastructure.ai.prescription_runtime import PRESCRIPTION_V1_SCHEMA

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
SOURCE = UUID("22222222-2222-2222-2222-222222222222")
DEFINITION = UUID("33333333-3333-3333-3333-333333333333")
FORMULA = UUID("44444444-4444-4444-4444-444444444444")
PROVIDER = UUID("55555555-5555-5555-5555-555555555555")
SERVICE = UUID("66666666-6666-6666-6666-666666666666")
ROUTING = UUID("77777777-7777-7777-7777-777777777777")
CORRELATION = "core-e2e"


class Recorder:
    def __init__(self) -> None:
        self.items: list[object] = []

    async def record(self, item: object) -> None:
        self.items.append(item)


class HouseholdRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, Household] = {}

    async def add(self, item: Household) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> Household | None:
        return self.items.get(item_id)

    async def get_by_case_code(self, case_code: str) -> Household | None:
        return next((x for x in self.items.values() if x.case_code == case_code), None)


class AssignmentRepo:
    def __init__(self) -> None:
        self.items: list[CaseAssignment] = []

    async def add(self, item: CaseAssignment) -> None:
        self.items.append(item)

    async def has_active_assignment(
        self, *, household_id: UUID, actor_id: UUID
    ) -> bool:
        return any(
            x.household_id == household_id and x.actor_id == actor_id
            for x in self.items
        )


class SourceRepo:
    async def get(self, source_id: UUID) -> DataSource | None:
        if source_id != SOURCE:
            return None
        return DataSource(
            SOURCE,
            "CASEWORKER",
            SourceType.EXPERT_ASSESSMENT,
            "Caseworker",
            True,
        )

    async def list_active(self) -> list[DataSource]:
        item = await self.get(SOURCE)
        return [] if item is None else [item]


class FactRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, HouseholdFact] = {}

    async def add(self, item: HouseholdFact) -> None:
        self.items[item.id] = item

    async def get_for_household(
        self, *, household_id: UUID, fact_id: UUID
    ) -> HouseholdFact | None:
        item = self.items.get(fact_id)
        return item if item is not None and item.household_id == household_id else None

    async def list_for_household(self, household_id: UUID) -> list[HouseholdFact]:
        return [x for x in self.items.values() if x.household_id == household_id]


class FactValidationRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, FactValidationState] = {}

    async def create_initial(
        self, *, state: FactValidationState, occurred_at: datetime
    ) -> None:
        self.items[state.fact_id] = state

    async def get_state(self, fact_id: UUID) -> FactValidationState | None:
        return self.items.get(fact_id)

    async def transition(
        self, *, previous: FactValidationState, current: FactValidationState
    ) -> None:
        assert self.items[previous.fact_id].version == previous.version
        self.items[current.fact_id] = current
