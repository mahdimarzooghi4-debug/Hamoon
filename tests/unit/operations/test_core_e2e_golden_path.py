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
        )


class PrescriptionRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, Prescription] = {}
        self.line_items: dict[UUID, PrescriptionItem] = {}

    async def add(self, item: Prescription) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> Prescription | None:
        return self.items.get(item_id)

    async def update(self, item: Prescription, *, expected_version: int) -> None:
        assert self.items[item.id].version == expected_version
        self.items[item.id] = item

    async def add_items(self, items: tuple[PrescriptionItem, ...]) -> None:
        for item in items:
            self.line_items[item.id] = item

    async def get_item(
        self, *, prescription_id: UUID, item_id: UUID
    ) -> PrescriptionItem | None:
        item = self.line_items.get(item_id)
        if item is None or item.prescription_id != prescription_id:
            return None
        return item

    async def get_item_by_id(self, item_id: UUID) -> PrescriptionItem | None:
        return self.line_items.get(item_id)

    async def list_items(self, prescription_id: UUID) -> list[PrescriptionItem]:
        return [
            x for x in self.line_items.values() if x.prescription_id == prescription_id
        ]

    async def mark_item_activated(self, item_id: UUID) -> None:
        item = self.line_items[item_id]
        self.line_items[item_id] = replace(
            item,
            status=PrescriptionItemStatus.ACTIVATED,
        )


class InterventionRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, Intervention] = {}

    async def add(self, item: Intervention) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> Intervention | None:
        return self.items.get(item_id)

    async def get_by_prescription_item(
        self, prescription_item_id: UUID
    ) -> Intervention | None:
        return next(
            (
                x
                for x in self.items.values()
                if x.prescription_item_id == prescription_item_id
            ),
            None,
        )

    async def list_for_household(self, household_id: UUID) -> list[Intervention]:
        return [x for x in self.items.values() if x.household_id == household_id]


class Registry:
    async def get_provider(self, provider_id: UUID) -> Provider | None:
        if provider_id != PROVIDER:
            return None
        return Provider(
            PROVIDER,
            "provider",
            "Provider",
            ProviderStatus.ACTIVE,
            None,
            "API",
            datetime.now(UTC),
        )

    async def list_providers(self) -> list[Provider]:
        item = await self.get_provider(PROVIDER)
        return [] if item is None else [item]

    async def get_service(self, service_id: UUID) -> ProviderService | None:
        if service_id != SERVICE:
            return None
        return ProviderService(
            id=SERVICE,
            provider_id=PROVIDER,
            service_type="EMPLOYMENT_MARKET",
            title="Market linkage",
            description="",
            supported_intervention_types=(InterventionType.MARKET_LINKAGE,),
            eligibility_policy_version="eligibility-v1",
            coverage_policy_version="coverage-v1",
            coverage_fact_type="geo.coverage_code",
            coverage_codes=("BAKU-1",),
            sla_policy_version=None,
            active=True,
        )

    async def list_services_for_provider(
        self, provider_id: UUID
    ) -> list[ProviderService]:
        item = await self.get_service(SERVICE)
        return [] if provider_id != PROVIDER or item is None else [item]

    async def list_services_by_type(self, service_type: str) -> list[ProviderService]:
        item = await self.get_service(SERVICE)
        if item is None or service_type != "EMPLOYMENT_MARKET":
            return []
        return [item]

    async def list_eligibility_rules(
        self, provider_service_id: UUID
    ) -> list[ProviderEligibilityRule]:
        if provider_service_id != SERVICE:
            return []
        return [
            ProviderEligibilityRule(
                id=uuid4(),
                provider_service_id=SERVICE,
                fact_type="geo.coverage_code",
                operator=EligibilityOperator.EXISTS,
                expected_value=None,
                reason_code="COVERAGE_FACT_REQUIRED",
                active=True,
            )
        ]

    async def latest_capacity(
        self, provider_service_id: UUID
    ) -> ProviderCapacitySnapshot | None:
        if provider_service_id != SERVICE:
            return None
        return ProviderCapacitySnapshot(
            id=uuid4(),
            provider_service_id=SERVICE,
            capacity_status=CapacityStatus.AVAILABLE,
            available_slots=5,
            valid_at=datetime.now(UTC),
            received_at=datetime.now(UTC),
            source_reference="core-e2e",
        )


class MatchRepo:
    def __init__(self) -> None:
        self.item: ProviderMatch | None = None

    async def add(self, item: ProviderMatch) -> None:
        self.item = item

    async def get(self, item_id: UUID) -> ProviderMatch | None:
        return self.item if self.item is not None and self.item.id == item_id else None

    async def get_latest_for_intervention(
        self, intervention_id: UUID
    ) -> ProviderMatch | None:
        if self.item is None or self.item.intervention_id != intervention_id:
            return None
        return self.item

    async def get_candidate(
        self,
        *,
        provider_match_id: UUID,
        provider_id: UUID,
        provider_service_id: UUID,
    ):
        if self.item is None or self.item.id != provider_match_id:
            return None
        return next(
            (
                x
                for x in self.item.candidates
                if x.provider_id == provider_id
                and x.provider_service_id == provider_service_id
            ),
            None,
        )


class SelectionRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, ProviderSelection] = {}

    async def add(self, item: ProviderSelection) -> None:
        self.items[item.id] = item


class ReferralRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, Referral] = {}
        self.events: list[ReferralEvent] = []

    async def add(self, item: Referral) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> Referral | None:
        return self.items.get(item_id)

    async def get_by_provider_reference(
        self, *, provider_id: UUID, external_referral_id: str
    ) -> Referral | None:
        return next(
            (
                x
                for x in self.items.values()
                if x.provider_id == provider_id
                and x.external_referral_id == external_referral_id
            ),
            None,
        )

    async def update(self, item: Referral, *, expected_version: int) -> None:
        assert self.items[item.id].version == expected_version
        self.items[item.id] = item

    async def add_event(self, item: ReferralEvent) -> None:
        self.events.append(item)

    async def list_events(self, item_id: UUID) -> list[ReferralEvent]:
        return [x for x in self.events if x.referral_id == item_id]

    async def mark_data_items_shared(
        self,
        *,
        referral_id: UUID,
        shared_at: datetime,
        authorization_basis: str,
    ) -> None:
        current = self.items[referral_id]
        self.items[referral_id] = replace(
            current,
            data_items=tuple(
                replace(
                    item,
                    shared_at=shared_at,
                    authorization_basis=authorization_basis,
                )
                for item in current.data_items
            ),
        )


class DispatchRepo:
    def __init__(self) -> None:
        self.items: dict[str, ReferralDispatch] = {}

    async def add(self, item: ReferralDispatch) -> None:
        self.items[item.idempotency_key] = item

    async def get_by_idempotency_key(
        self, key: str
    ) -> ReferralDispatch | None:
        return self.items.get(key)

    async def get(self, dispatch_id: UUID) -> ReferralDispatch | None:
        return next((x for x in self.items.values() if x.id == dispatch_id), None)

    async def get_latest_for_referral(
        self, referral_id: UUID
    ) -> ReferralDispatch | None:
        return next(
            (x for x in self.items.values() if x.referral_id == referral_id),
            None,
        )


class ResultRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, ProviderResult] = {}

    async def add(self, item: ProviderResult) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> ProviderResult | None:
        return self.items.get(item_id)

    async def get_by_external_result(
        self, *, provider_id: UUID, external_result_id: str
    ) -> ProviderResult | None:
        return next(
            (
                x
                for x in self.items.values()
                if x.provider_id == provider_id
                and x.external_result_id == external_result_id
            ),
            None,
        )

    async def list_for_referral(self, referral_id: UUID) -> list[ProviderResult]:
        return [x for x in self.items.values() if x.referral_id == referral_id]


class PlanRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, ReassessmentPlan] = {}

    async def add(self, item: ReassessmentPlan) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> ReassessmentPlan | None:
        return self.items.get(item_id)

    async def get_by_provider_result(
        self, provider_result_id: UUID
    ) -> ReassessmentPlan | None:
        return next(
            (
                x
                for x in self.items.values()
                if x.provider_result_id == provider_result_id
            ),
            None,
        )

    async def get_by_outcome(self, outcome_id: UUID) -> ReassessmentPlan | None:
        return next(
            (x for x in self.items.values() if x.outcome_id == outcome_id),
            None,
        )

    async def update(self, item: ReassessmentPlan, *, expected_version: int) -> None:
        assert self.items[item.id].version == expected_version
        self.items[item.id] = item


class WorkItemRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, WorkItem] = {}

    async def add(self, item: WorkItem) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> WorkItem | None:
        return self.items.get(item_id)

    async def update(self, item: WorkItem, *, expected_version: int) -> None:
        assert self.items[item.id].version == expected_version
        self.items[item.id] = item


class OutcomeRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, HamoonOutcome] = {}

    async def add(self, item: HamoonOutcome) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> HamoonOutcome | None:
        return self.items.get(item_id)

    async def get_by_post_assessment(
        self, post_assessment_id: UUID
    ) -> HamoonOutcome | None:
        return next(
            (
                x
                for x in self.items.values()
                if x.post_assessment_id == post_assessment_id
            ),
            None,
        )

    async def update(self, item: HamoonOutcome, *, expected_version: int) -> None:
        assert self.items[item.id].version == expected_version
        self.items[item.id] = item


async def _measure(
    *,
    assessment: Assessment,
    scores: tuple[str, str, str, str],
    definitions: DefinitionRepo,
    source: SourceRepo,
    assessments: AssessmentRepo,
    observations: ObservationRepo,
    validations: ObservationValidationRepo,
    accepted: AcceptedObservationRepo,
    snapshots: SnapshotRepo,
    events: Recorder,
    audits: Recorder,
) -> PGORSnapshot:
    for indicator, score in zip(
        definitions.bundle.indicators,
        scores,
        strict=True,
    ):
        observation, validation = await RecordIndicatorObservationHandler(
            assessments=assessments,
            definitions=definitions,
            sources=source,
            observations=observations,
            validations=validations,
            events=events,
            audits=audits,
        ).handle(
            RecordIndicatorObservationCommand(
                assessment_id=assessment.id,
                actor_id=ACTOR,
                indicator_definition_id=indicator.id,
                raw_score_0_100=Decimal(score),
                source_id=SOURCE,
                source_detail=None,
                effective_at=datetime.now(UTC),
                request_id=f"observe-{indicator.code}",
                correlation_id=CORRELATION,
            )
        )
        await ChangeObservationValidationHandler(
            observations=observations,
            validations=validations,
            events=events,
            audits=audits,
        ).handle(
            ChangeObservationValidationCommand(
                assessment_id=assessment.id,
                observation_id=observation.id,
                actor_id=ACTOR,
                to_status=ObservationValidationStatus.VALIDATED,
                expected_validation_version=validation.version,
                reason_code="HUMAN_REVIEW",
                reason_text=None,
                request_id=f"validate-{indicator.code}",
                correlation_id=CORRELATION,
            )
        )
        await ResolveAcceptedObservationHandler(
            observations=observations,
            validations=validations,
            accepted_observations=accepted,
            events=events,
            audits=audits,
        ).handle(
            ResolveAcceptedObservationCommand(
                assessment_id=assessment.id,
                indicator_definition_id=indicator.id,
                observation_id=observation.id,
                actor_id=ACTOR,
                expected_projection_version=0,
                reason_code="HUMAN_RESOLUTION",
                reason_text=None,
                request_id=f"accept-{indicator.code}",
                correlation_id=CORRELATION,
            )
        )

    return await CalculateOfficialPGORHandler(
        assessments=assessments,
        definitions=definitions,
        accepted_observations=accepted,
        observations=observations,
        validations=validations,
        formulas=FormulaRepo(),
        snapshots=snapshots,
        events=events,
        audits=audits,
    ).handle(
        CalculateOfficialPGORCommand(
            assessment_id=assessment.id,
            formula_version_id=FORMULA,
            actor_id=ACTOR,
            request_id="calculate-pgor",
            correlation_id=CORRELATION,
        )
    )


@pytest.mark.asyncio
async def test_core_e2e_household_to_outcome_learning_signal() -> None:
    events = Recorder()
    audits = Recorder()
    households = HouseholdRepo()
    assignments = AssignmentRepo()
    facts = FactRepo()
    fact_validations = FactValidationRepo()
    accepted_state = AcceptedStateRepo()
    definitions = DefinitionRepo()
    assessments = AssessmentRepo()
    observations = ObservationRepo()
    observation_validations = ObservationValidationRepo(observations)
    accepted_observations = AcceptedObservationRepo()
    snapshots = SnapshotRepo()
    features = FeatureRepo()
    ai_decisions = AIDecisionRepo()
    diagnoses = DiagnosisRepo()
    humans = HumanRepo()
    learning = LearningRepo()
    traces = TraceRepo()
    prescriptions = PrescriptionRepo()
    interventions = InterventionRepo()
    matches = MatchRepo()
    selections = SelectionRepo()
    referrals = ReferralRepo()
    dispatches = DispatchRepo()
    results = ResultRepo()
    plans = PlanRepo()
    work_items = WorkItemRepo()
    outcomes = OutcomeRepo()
    source = SourceRepo()
    registry = Registry()

    household = await CreateHouseholdHandler(
        households=households,
        assignments=assignments,
        events=events,
        audits=audits,
    ).handle(
        CreateHouseholdCommand(
            case_code="H-CORE-E2E",
            actor_id=ACTOR,
            organizational_unit_id="unit-e2e",
            request_id="create-household",
            correlation_id=CORRELATION,
        )
    )

    fact = await RecordHouseholdFactHandler(
        sources=source,
        facts=facts,
        validations=fact_validations,
        events=events,
        audits=audits,
    ).handle(
        RecordHouseholdFactCommand(
            household_id=household.id,
            actor_id=ACTOR,
            fact_type="geo.coverage_code",
            value_type=FactValueType.CODE,
            value="BAKU-1",
            source_id=SOURCE,
            source_detail=None,
            effective_from=datetime.now(UTC),
            request_id="record-fact",
            correlation_id=CORRELATION,
        )
    )
    validated_fact = await ChangeFactValidationHandler(
        facts=facts,
        validations=fact_validations,
        events=events,
        audits=audits,
    ).handle(
        ChangeFactValidationCommand(
            household_id=household.id,
            fact_id=fact.id,
            actor_id=ACTOR,
            to_status=FactValidationStatus.VALIDATED,
            expected_validation_version=1,
            reason_code="HUMAN_REVIEW",
            reason_text=None,
            request_id="validate-fact",
            correlation_id=CORRELATION,
        )
    )
    assert validated_fact.status is FactValidationStatus.VALIDATED
    accepted_fact = await ResolveAcceptedFactHandler(
        facts=facts,
        validations=fact_validations,
        accepted_state=accepted_state,
        events=events,
        audits=audits,
    ).handle(
        ResolveAcceptedFactCommand(
            household_id=household.id,
            fact_type="geo.coverage_code",
            fact_id=fact.id,
            actor_id=ACTOR,
            expected_projection_version=0,
            reason_code="HUMAN_RESOLUTION",
            reason_text=None,
            request_id="accept-fact",
            correlation_id=CORRELATION,
        )
    )

    baseline = await StartAssessmentHandler(
        assessments=assessments,
        definitions=definitions,
        events=events,
        audits=audits,
    ).handle(
        StartAssessmentCommand(
            household_id=household.id,
            actor_id=ACTOR,
            assessment_type=AssessmentType.BASELINE,
            definition_version_id=DEFINITION,
            reason="baseline",
            request_id="start-baseline",
            correlation_id=CORRELATION,
        )
    )
    pre_snapshot = await _measure(
        assessment=baseline,
        scores=("70", "65", "30", "55"),
        definitions=definitions,
        source=source,
        assessments=assessments,
        observations=observations,
        validations=observation_validations,
        accepted=accepted_observations,
        snapshots=snapshots,
        events=events,
        audits=audits,
    )

    diagnosis, _ = await GenerateDiagnosisHandler(
        snapshots=snapshots,
        definitions=definitions,
        feature_packages=features,
        ai_decisions=ai_decisions,
        diagnoses=diagnoses,
        traces=traces,
        ai_client=DiagnosisAI(),
        accepted_state=accepted_state,
        events=events,
        audits=audits,
    ).handle(
        GenerateDiagnosisCommand(
            household_id=household.id,
            pgor_snapshot_id=pre_snapshot.id,
            actor_id=ACTOR,
            request_id="diagnosis-ai",
            correlation_id=CORRELATION,
        )
    )
    accepted_diagnosis, _, diagnosis_signal = await ReviewDiagnosisHandler(
        diagnoses=diagnoses,
        ai_decisions=ai_decisions,
        human_decisions=humans,
        feature_packages=features,
        traces=traces,
        learning_signals=learning,
        events=events,
        audits=audits,
        output_schema=DIAGNOSIS_V1_SCHEMA,
    ).handle(
        ReviewDiagnosisCommand(
            diagnosis_id=diagnosis.id,
            actor_id=ACTOR,
            action=HumanDecisionAction.CONFIRM,
            expected_version=diagnosis.version,
            reason_code=None,
            reason_text=None,
            modified_payload=None,
            request_id="review-diagnosis",
            correlation_id=CORRELATION,
        )
    )
    assert accepted_diagnosis.accepted_payload is not None
    assert diagnosis_signal.ai_decision_id == diagnosis.ai_decision_id

    prescription, _ = await GeneratePrescriptionHandler(
        snapshots=snapshots,
        diagnoses=diagnoses,
        ai_decisions=ai_decisions,
        feature_packages=features,
        prescriptions=prescriptions,
        traces=traces,
        ai_client=PrescriptionAI(),
        accepted_state=accepted_state,
        events=events,
        audits=audits,
    ).handle(
        GeneratePrescriptionCommand(
            household_id=household.id,
            diagnosis_id=accepted_diagnosis.id,
            pgor_snapshot_id=pre_snapshot.id,
            actor_id=ACTOR,
            request_id="prescription-ai",
            correlation_id=CORRELATION,
        )
    )
    approved, _, prescription_signal, prescription_items = (
        await ReviewPrescriptionHandler(
            prescriptions=prescriptions,
            ai_decisions=ai_decisions,
            feature_packages=features,
            human_decisions=humans,
            learning_signals=learning,
            traces=traces,
            events=events,
            audits=audits,
            output_schema=PRESCRIPTION_V1_SCHEMA,
        ).handle(
            ReviewPrescriptionCommand(
                prescription_id=prescription.id,
                actor_id=ACTOR,
                action=HumanDecisionAction.CONFIRM,
                expected_version=prescription.version,
                reason_code=None,
                reason_text=None,
                modified_payload=None,
                request_id="review-prescription",
                correlation_id=CORRELATION,
            )
        )
    )
    assert approved.accepted_payload is not None
    assert prescription_signal.prescription_id == prescription.id

    intervention = await ActivateInterventionHandler(
        prescriptions=prescriptions,
        interventions=interventions,
        traces=traces,
        events=events,
        audits=audits,
    ).handle(
        ActivateInterventionCommand(
            prescription_id=prescription.id,
            prescription_item_id=prescription_items[0].id,
            actor_id=ACTOR,
            request_id="activate-intervention",
            correlation_id=CORRELATION,
        )
    )

    context_version = await accepted_state.context_version(household.id)
    match = await MatchProvidersHandler(
        interventions=interventions,
        accepted_state=accepted_state,
        registry=registry,
        matches=matches,
        events=events,
        audits=audits,
    ).handle(
        MatchProvidersCommand(
            intervention_id=intervention.id,
            service_type="EMPLOYMENT_MARKET",
            household_context_version=context_version,
            actor_id=ACTOR,
            request_id="provider-match",
            correlation_id=CORRELATION,
        )
    )
    assert len(match.candidates) == 1

    referral, _, _, provider_signal = await CreateReferralHandler(
        interventions=interventions,
        registry=registry,
