from datetime import UTC, datetime
from uuid import uuid4

from hamoon.app.observability.metrics import PGOR_CALCULATIONS
from hamoon.domains.assessment.application.handlers import (
    EvaluateAssessmentReadinessHandler,
)
from hamoon.domains.assessment.domain.entities import AssessmentReadinessStatus
from hamoon.domains.assessment.domain.errors import AssessmentNotFoundError
from hamoon.domains.assessment.ports.repositories import (
    AcceptedObservationRepository,
    AssessmentRepository,
    IndicatorObservationRepository,
    ObservationValidationRepository,
)
from hamoon.domains.pgor.application.commands import CalculateOfficialPGORCommand
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import (
    AcceptedIndicatorInput,
    FormulaStatus,
    PGORSnapshotStatus,
    calculate_pgor,
)
from hamoon.domains.pgor.domain.errors import (
    FormulaVersionNotFoundError,
    PGORCalculationBlockedError,
)
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.pgor.ports.repositories import (
    PGORDefinitionRepository,
    PGORFormulaRepository,
    PGORSnapshotRepository,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder

ENGINE_VERSION = "1.0.0"
SCORING_VERSION = "raw-0-100-v1"


class CalculateOfficialPGORHandler:
    def __init__(
        self,
        *,
        assessments: AssessmentRepository,
        definitions: PGORDefinitionRepository,
        accepted_observations: AcceptedObservationRepository,
        observations: IndicatorObservationRepository,
        validations: ObservationValidationRepository,
        formulas: PGORFormulaRepository,
        snapshots: PGORSnapshotRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._assessments = assessments
        self._definitions = definitions
        self._accepted_observations = accepted_observations
        self._observations = observations
        self._validations = validations
        self._formulas = formulas
        self._snapshots = snapshots
        self._events = events
        self._audits = audits

    async def handle(self, command: CalculateOfficialPGORCommand) -> PGORSnapshot:
        assessment = await self._assessments.get(command.assessment_id)
        if assessment is None:
            raise AssessmentNotFoundError(str(command.assessment_id))

        readiness = await EvaluateAssessmentReadinessHandler(
            assessments=self._assessments,
            definitions=self._definitions,
            accepted_observations=self._accepted_observations,
            validations=self._validations,
        ).handle(assessment.id)
        if readiness.status is not AssessmentReadinessStatus.READY:
            PGOR_CALCULATIONS.labels(mode="official", status="blocked").inc()
            raise PGORCalculationBlockedError(
                ",".join(readiness.blocking_reasons) or readiness.status.value
            )

        formula = (
            await self._formulas.get(command.formula_version_id)
            if command.formula_version_id is not None
            else await self._formulas.get_active()
        )
        if formula is None:
            PGOR_CALCULATIONS.labels(mode="official", status="formula_missing").inc()
            raise FormulaVersionNotFoundError(
                str(command.formula_version_id or "ACTIVE_FORMULA")
            )
        now = datetime.now(UTC)
        if (
            formula.status is not FormulaStatus.ACTIVE
            or formula.approved_at is None
            or formula.effective_from is None
            or formula.effective_from > now
            or not formula.production_eligible
        ):
            PGOR_CALCULATIONS.labels(mode="official", status="blocked").inc()
            raise PGORCalculationBlockedError("FORMULA_NOT_PRODUCTION_ACTIVE")
        formula.validate_coefficients()

        bundle = await self._definitions.get_bundle(assessment.definition_version_id)
        if bundle is None:
            PGOR_CALCULATIONS.labels(mode="official", status="blocked").inc()
            raise PGORCalculationBlockedError("PGOR_DEFINITION_NOT_AVAILABLE")

        variables_by_id = {item.id: item for item in bundle.variables}
        dimensions_by_id = {item.id: item for item in bundle.dimensions}
        indicators_by_id = {item.id: item for item in bundle.indicators}

        accepted = await self._accepted_observations.list_for_assessment(assessment.id)
        engine_inputs: list[AcceptedIndicatorInput] = []

        for projection in accepted:
            observation = await self._observations.get_for_assessment(
                assessment_id=assessment.id,
                observation_id=projection.observation_id,
            )
            indicator = indicators_by_id.get(projection.indicator_definition_id)
            if observation is None or indicator is None:
                raise PGORCalculationBlockedError("ACCEPTED_INPUT_NOT_REPRODUCIBLE")

            dimension = dimensions_by_id.get(indicator.dimension_definition_id)
            if dimension is None:
                raise PGORCalculationBlockedError("PGOR_DIMENSION_NOT_FOUND")
            variable = variables_by_id.get(dimension.variable_definition_id)
            if variable is None:
                raise PGORCalculationBlockedError("PGOR_VARIABLE_NOT_FOUND")

            engine_inputs.append(
                AcceptedIndicatorInput(
                    observation_id=observation.id,
                    observation_version=observation.version,
                    indicator_definition_id=indicator.id,
                    dimension_definition_id=dimension.id,
                    dimension_code=dimension.code,
                    variable_code=PGORVariableCode(variable.code),
                    raw_score_0_100=observation.raw_score_0_100,
                )
            )

        expected_dimension_ids = {item.id for item in bundle.dimensions}
        observed_dimension_ids = {
            item.dimension_definition_id for item in engine_inputs
        }
        missing_dimension_ids = expected_dimension_ids - observed_dimension_ids
        if missing_dimension_ids:
            PGOR_CALCULATIONS.labels(mode="official", status="blocked").inc()
            raise PGORCalculationBlockedError("MISSING_PGOR_DIMENSION_DATA")

        result = calculate_pgor(
            accepted_inputs=tuple(engine_inputs),
            definition_version_id=assessment.definition_version_id,
            formula=formula,
            scoring_version=SCORING_VERSION,
            engine_version=ENGINE_VERSION,
        )

        data_quality_flags = (
            ("HAS_UNRESOLVED_OBSERVATION",)
            if readiness.unresolved_validation_count > 0
            else ()
        )
        snapshot = await self._snapshots.create(
            household_id=assessment.household_id,
            assessment_id=assessment.id,
            definition_version_id=assessment.definition_version_id,
            formula_version_id=formula.id,
            engine_version=ENGINE_VERSION,
            scoring_version=SCORING_VERSION,
            status=PGORSnapshotStatus.OFFICIAL,
            result=result,
            completeness_ratio=readiness.completeness_ratio,
            data_quality_flags=data_quality_flags,
            calculated_at=now,
            calculated_by=command.actor_id,
        )

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="PGORSnapshotCalculated",
                event_version=1,
                aggregate_type="ASSESSMENT",
                aggregate_id=assessment.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "snapshot_id": str(snapshot.id),
                    "household_id": str(snapshot.household_id),
                    "assessment_id": str(snapshot.assessment_id),
                    "P": str(snapshot.p),
                    "G": str(snapshot.g),
                    "O": str(snapshot.o),
                    "R": str(snapshot.r),
                    "E": str(snapshot.e),
                    "bottleneck_variables": [
                        code.value for code in snapshot.bottleneck_variables
                    ],
                    "formula_version_id": str(snapshot.formula_version_id),
                    "definition_version_id": str(snapshot.definition_version_id),
                    "engine_version": snapshot.engine_version,
                    "scoring_version": snapshot.scoring_version,
                    "calculated_at": snapshot.calculated_at.isoformat(),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="pgor.snapshot.calculate",
                resource_type="PGOR_SNAPSHOT",
                resource_id=snapshot.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="EMPOWERMENT_ASSESSMENT",
                metadata={
                    "event_id": str(event_id),
                    "assessment_id": str(assessment.id),
                    "input_fingerprint": snapshot.input_fingerprint,
                    "formula_version_id": str(formula.id),
                    "engine_version": ENGINE_VERSION,
                    "scoring_version": SCORING_VERSION,
                },
            )
        )
        PGOR_CALCULATIONS.labels(mode="official", status="success").inc()
        return snapshot
