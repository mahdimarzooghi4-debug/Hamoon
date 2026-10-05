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


class AcceptedStateRepo:
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, str], CurrentAcceptedFact] = {}

    async def get(
        self, *, household_id: UUID, fact_type: str
    ) -> CurrentAcceptedFact | None:
        return self.items.get((household_id, fact_type))

    async def list_for_household(self, household_id: UUID) -> list[CurrentAcceptedFact]:
        return [x for (hid, _), x in self.items.items() if hid == household_id]

    async def set_current(
        self,
        *,
        accepted: CurrentAcceptedFact,
        previous_fact_id: UUID | None,
        reason_code: str,
        reason_text: str | None,
        event_id: UUID,
    ) -> None:
        self.items[(accepted.household_id, accepted.fact_type)] = accepted

    async def context_version(self, household_id: UUID) -> int:
        return sum(
            item.projection_version
            for (hid, _), item in self.items.items()
            if hid == household_id
        )


class DefinitionRepo:
    def __init__(self) -> None:
        self.version = PGORDefinitionVersion(
            id=DEFINITION,
            code="core-e2e",
            version="1",
            status=PGORDefinitionStatus.ACTIVE,
            requirement_policy_status=RequirementPolicyStatus.RESOLVED,
            source_reference="core-e2e",
        )
        variables: list[PGORVariableDefinition] = []
        dimensions: list[PGORDimensionDefinition] = []
        indicators: list[PGORIndicatorDefinition] = []
        for index, code in enumerate(PGORVariableCode, start=1):
            variable_id = UUID(f"80000000-0000-0000-0000-{index:012d}")
            dimension_id = UUID(f"81000000-0000-0000-0000-{index:012d}")
            indicator_id = UUID(f"82000000-0000-0000-0000-{index:012d}")
            variables.append(
                PGORVariableDefinition(variable_id, DEFINITION, code, code.value, index)
            )
            dimensions.append(
                PGORDimensionDefinition(
                    dimension_id,
                    variable_id,
                    f"{code.value.lower()}-dimension",
                    code.value,
                    index,
                )
            )
            indicators.append(
                PGORIndicatorDefinition(
                    indicator_id,
                    dimension_id,
                    f"{code.value.lower()}-indicator",
                    code.value,
                    0,
                    100,
                    True,
                    True,
                    1,
                )
            )
        self.bundle = PGORDefinitionBundle(
            self.version,
            tuple(variables),
            tuple(dimensions),
            tuple(indicators),
        )

    async def get_active_bundle(self) -> PGORDefinitionBundle:
        return self.bundle

    async def get_bundle(
        self, definition_version_id: UUID
    ) -> PGORDefinitionBundle | None:
        return self.bundle if definition_version_id == DEFINITION else None

    async def get_version(
        self, definition_version_id: UUID
    ) -> PGORDefinitionVersion | None:
        return self.version if definition_version_id == DEFINITION else None

    async def list_indicators(
        self, definition_version_id: UUID
    ) -> list[PGORIndicatorDefinition]:
        if definition_version_id != DEFINITION:
            return []
        return list(self.bundle.indicators)

    async def get_indicator(
        self, *, definition_version_id: UUID, indicator_id: UUID
    ) -> PGORIndicatorDefinition | None:
        if definition_version_id != DEFINITION:
            return None
        return next((x for x in self.bundle.indicators if x.id == indicator_id), None)


class AssessmentRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, Assessment] = {}

    async def add(self, item: Assessment) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> Assessment | None:
        return self.items.get(item_id)


class ObservationRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, IndicatorObservation] = {}

    async def add(self, item: IndicatorObservation) -> None:
        self.items[item.id] = item

    async def get_for_assessment(
        self, *, assessment_id: UUID, observation_id: UUID
    ) -> IndicatorObservation | None:
        item = self.items.get(observation_id)
        if item is None or item.assessment_id != assessment_id:
            return None
        return item

    async def list_for_assessment(
        self, assessment_id: UUID
    ) -> list[IndicatorObservation]:
        return [x for x in self.items.values() if x.assessment_id == assessment_id]


class ObservationValidationRepo:
    def __init__(self, observations: ObservationRepo) -> None:
        self.observations = observations
        self.items: dict[UUID, ObservationValidationState] = {}

    async def create_initial(self, state: ObservationValidationState) -> None:
        self.items[state.observation_id] = state

    async def get_state(
        self, observation_id: UUID
    ) -> ObservationValidationState | None:
        return self.items.get(observation_id)

    async def transition(
        self,
        *,
        previous: ObservationValidationState,
        current: ObservationValidationState,
    ) -> None:
        assert self.items[previous.observation_id].version == previous.version
        self.items[current.observation_id] = current

    async def count_unresolved_for_assessment(self, assessment_id: UUID) -> int:
        return sum(
            1
            for observation_id, state in self.items.items()
            if self.observations.items[observation_id].assessment_id == assessment_id
            and state.status
            in {
                ObservationValidationStatus.PENDING_VALIDATION,
                ObservationValidationStatus.DISPUTED,
            }
        )


class AcceptedObservationRepo:
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, UUID], AcceptedIndicatorObservation] = {}

    async def get(
        self, *, assessment_id: UUID, indicator_definition_id: UUID
    ) -> AcceptedIndicatorObservation | None:
        return self.items.get((assessment_id, indicator_definition_id))

    async def list_for_assessment(
        self, assessment_id: UUID
    ) -> list[AcceptedIndicatorObservation]:
        return [x for (aid, _), x in self.items.items() if aid == assessment_id]

    async def set_current(
        self,
        *,
        accepted: AcceptedIndicatorObservation,
        previous_observation_id: UUID | None,
        reason_code: str,
        reason_text: str | None,
        event_id: UUID,
    ) -> None:
        key = (accepted.assessment_id, accepted.indicator_definition_id)
        self.items[key] = accepted


class FormulaRepo:
    def __init__(self) -> None:
        self.formula = FormulaVersion(
            FORMULA,
            "core-e2e",
            "1",
            FormulaStatus.ACTIVE,
            Decimal("0.34"),
            Decimal("0.33"),
            Decimal("0.33"),
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, tzinfo=UTC),
            True,
        )

    async def get(self, formula_version_id: UUID) -> FormulaVersion | None:
        return self.formula if formula_version_id == FORMULA else None

    async def get_active(self) -> FormulaVersion:
        return self.formula


class SnapshotRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, PGORSnapshot] = {}
        self.inputs: dict[UUID, list[PGORSnapshotInput]] = {}

    async def create(self, **kwargs) -> PGORSnapshot:
        result = kwargs["result"]
        snapshot_id = uuid4()
        snapshot = PGORSnapshot(
            id=snapshot_id,
            household_id=kwargs["household_id"],
            assessment_id=kwargs["assessment_id"],
            definition_version_id=kwargs["definition_version_id"],
            formula_version_id=kwargs["formula_version_id"],
            engine_version=kwargs["engine_version"],
            scoring_version=kwargs["scoring_version"],
            status=kwargs["status"],
            p=result.p,
            g=result.g,
            o=result.o,
            r=result.r,
            e=result.e,
            bottleneck_variables=result.bottleneck_variables,
            e_band=result.e_band,
            p_band=result.p_band,
            r_band=result.r_band,
            completeness_ratio=kwargs["completeness_ratio"],
            data_quality_flags=kwargs["data_quality_flags"],
            input_fingerprint=result.input_fingerprint,
            calculated_at=kwargs["calculated_at"],
            calculated_by=kwargs["calculated_by"],
        )
        self.items[snapshot_id] = snapshot
        self.inputs[snapshot_id] = [
            PGORSnapshotInput(
                snapshot_id=snapshot_id,
                observation_id=x.observation_id,
                observation_version=x.observation_version,
                indicator_definition_id=x.indicator_definition_id,
                dimension_definition_id=x.dimension_definition_id,
                variable_code=x.variable_code,
                raw_score_0_100=x.raw_score_0_100,
                normalized_score=x.normalized_score,
            )
            for x in result.normalized_inputs
        ]
        return snapshot

    async def get(self, snapshot_id: UUID) -> PGORSnapshot | None:
        return self.items.get(snapshot_id)

    async def list_inputs(self, snapshot_id: UUID) -> list[PGORSnapshotInput]:
        return self.inputs.get(snapshot_id, [])

    async def get_official_by_assessment(
        self, assessment_id: UUID
    ) -> PGORSnapshot | None:
        candidates = [
            x for x in self.items.values() if x.assessment_id == assessment_id
        ]
        return candidates[-1] if candidates else None


class FeatureRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, FeaturePackage] = {}

    async def add(self, item: FeaturePackage) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> FeaturePackage | None:
        return self.items.get(item_id)

    async def get_by_snapshot(
        self, *, snapshot_id: UUID, schema_version: str
    ) -> FeaturePackage | None:
        return next(
            (
                x
                for x in self.items.values()
                if x.pgor_snapshot_id == snapshot_id
                and x.schema_version == schema_version
            ),
            None,
        )


class AIDecisionRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, AIDecision] = {}

    async def add(self, item: AIDecision) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> AIDecision | None:
        return self.items.get(item_id)


class DiagnosisRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, Diagnosis] = {}

    async def add(self, item: Diagnosis) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> Diagnosis | None:
        return self.items.get(item_id)

    async def update(self, item: Diagnosis, *, expected_version: int) -> None:
        assert self.items[item.id].version == expected_version
        self.items[item.id] = item


class HumanRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, HumanDecision] = {}

    async def add(self, item: HumanDecision) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> HumanDecision | None:
        return self.items.get(item_id)


class LearningRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, LearningSignal] = {}

    async def add(self, item: LearningSignal) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> LearningSignal | None:
        return self.items.get(item_id)


class TraceRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, DecisionTrace] = {}

    async def add(self, item: DecisionTrace) -> None:
        self.items[item.ai_decision_id] = item

    async def get_by_ai_decision(
        self, ai_decision_id: UUID
    ) -> DecisionTrace | None:
        return self.items.get(ai_decision_id)

    async def attach_human_decision(
        self,
        *,
        ai_decision_id: UUID,
        human_decision_id: UUID,
        learning_signal_id: UUID | None = None,
        closed_at: datetime | None = None,
    ) -> None:
        current = self.items[ai_decision_id]
        self.items[ai_decision_id] = replace(
            current,
            human_decision_id=human_decision_id,
            learning_signal_id=learning_signal_id,
            closed_at=closed_at,
        )

    async def attach_intervention(
        self, *, ai_decision_id: UUID, intervention_id: UUID
    ) -> None:
        current = self.items[ai_decision_id]
        self.items[ai_decision_id] = replace(
            current,
            intervention_id=intervention_id,
        )

    async def attach_referral(
        self, *, intervention_id: UUID, referral_id: UUID
    ) -> None:
        current = next(
            x for x in self.items.values() if x.intervention_id == intervention_id
        )
        self.items[current.ai_decision_id] = replace(
            current,
            referral_id=referral_id,
        )

    async def attach_provider_result(
        self, *, referral_id: UUID, provider_result_id: UUID
    ) -> None:
        current = next(x for x in self.items.values() if x.referral_id == referral_id)
        self.items[current.ai_decision_id] = replace(
            current,
            provider_result_id=provider_result_id,
        )

    async def attach_outcome(
        self, *, intervention_id: UUID, outcome_id: UUID
    ) -> None:
        current = next(
            x
            for x in self.items.values()
            if x.intervention_id == intervention_id and x.prescription_id is not None
        )
        self.items[current.ai_decision_id] = replace(current, outcome_id=outcome_id)


class DiagnosisAI:
    async def generate_diagnosis(
        self, *, feature_package: FeaturePackage, correlation_id: str
    ) -> AIExecutionResult:
        return AIExecutionResult(
            provider_code="FAKE",
            model_id="diagnosis-e2e",
            model_alias="hamoon.diagnosis.v1",
            routing_policy_id=ROUTING,
            routing_policy_version="e2e",
            prompt_policy_version="diagnosis-prompt-v1",
            output_schema_version="diagnosis-v1",
            output={
                "schema_version": "diagnosis-v1",
                "summary": "Opportunity is the current bottleneck.",
                "items": [
                    {
                        "code": "PGOR_BOTTLENECK_O",
                        "category": "NEED",
                        "title": "Opportunity constraint",
                        "rationale": "O is the minimum PGOR variable.",
                        "supporting_feature_refs": ["pgor.bottleneck_variables"],
                        "uncertainty": "LOW",
                    }
                ],
                "review_flags": ["HUMAN_REVIEW_REQUIRED"],
            },
        )


class PrescriptionAI:
    async def generate_prescription(
        self, *, feature_package: FeaturePackage, correlation_id: str
    ) -> AIExecutionResult:
        payload = feature_package.provider_payload()
        diagnosis_id = str(payload["diagnosis.id"])
        return AIExecutionResult(
            provider_code="FAKE",
            model_id="prescription-e2e",
            model_alias="hamoon.prescription.v1",
            routing_policy_id=ROUTING,
            routing_policy_version="e2e",
            prompt_policy_version="prescription-prompt-v1",
            output_schema_version="prescription-v1",
            output={
                "schema_version": "prescription-v1",
                "summary": "Opportunity-targeted intervention.",
                "intensity_score": payload["prescription.intensity_score"],
                "items": [
                    {
                        "code": "O_MARKET_LINKAGE",
                        "target_variable": "O",
                        "intervention_type": "MARKET_LINKAGE",
                        "priority_rank": 1,
                        "title": "Connect to market",
                        "rationale": "O is the current bottleneck.",
                        "success_criteria": ["Opportunity is reassessed."],
                        "review_schedule": {
                            "review_after_days": 30,
                            "rationale": "Measure observed change.",
                        },
                        "diagnosis_refs": [f"diagnosis:{diagnosis_id}"],
                        "supporting_feature_refs": [
                            "pgor.bottleneck_variables",
                            "prescription.intensity_score",
                            "diagnosis.accepted_payload",
                        ],
                    }
                ],
                "review_flags": ["HUMAN_REVIEW_REQUIRED"],
            },
