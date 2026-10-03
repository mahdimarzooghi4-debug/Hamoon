from datetime import UTC, datetime
from uuid import UUID, uuid4

from hamoon.domains.assessment.domain.entities import (
    Assessment,
    AssessmentStatus,
    AssessmentType,
)
from hamoon.domains.assessment.domain.errors import DefinitionNotAvailableError
from hamoon.domains.assessment.ports.repositories import AssessmentRepository
from hamoon.domains.intervention.ports.repositories import InterventionRepository
from hamoon.domains.pgor.domain.definitions import PGORDefinitionStatus
from hamoon.domains.pgor.ports.repositories import PGORDefinitionRepository
from hamoon.domains.provider_result.ports.repositories import ProviderResultRepository
from hamoon.domains.referral.ports.repositories import ReferralRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


class ReassessmentError(ValueError):
    """Re-assessment provenance or inputs are invalid."""


class StartReassessmentHandler:
    def __init__(
        self,
        *,
        assessments: AssessmentRepository,
        definitions: PGORDefinitionRepository,
        interventions: InterventionRepository,
        provider_results: ProviderResultRepository,
        referrals: ReferralRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._assessments = assessments
        self._definitions = definitions
        self._interventions = interventions
        self._provider_results = provider_results
        self._referrals = referrals
        self._events = events
        self._audits = audits

    async def handle(
        self,
        *,
        household_id: UUID,
        assessment_type: AssessmentType,
        definition_version_id: UUID,
        intervention_id: UUID,
        provider_result_id: UUID | None,
        parent_assessment_id: UUID | None,
        reason: str,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> Assessment:
        if assessment_type not in {
            AssessmentType.REASSESSMENT,
            AssessmentType.OUTCOME_REASSESSMENT,
        }:
            raise ReassessmentError("REASSESSMENT_TYPE_REQUIRED")
        if not reason.strip():
            raise ReassessmentError("REASSESSMENT_REASON_REQUIRED")

        definition = await self._definitions.get_version(definition_version_id)
        if definition is None or definition.status not in {
            PGORDefinitionStatus.APPROVED,
            PGORDefinitionStatus.ACTIVE,
        }:
            raise DefinitionNotAvailableError(str(definition_version_id))

        intervention = await self._interventions.get(intervention_id)
        if intervention is None or intervention.household_id != household_id:
            raise ReassessmentError("INTERVENTION_HOUSEHOLD_MISMATCH")

        if parent_assessment_id is not None:
            parent = await self._assessments.get(parent_assessment_id)
            if parent is None or parent.household_id != household_id:
                raise ReassessmentError("PARENT_ASSESSMENT_HOUSEHOLD_MISMATCH")

        if provider_result_id is not None:
            provider_result = await self._provider_results.get(provider_result_id)
            if provider_result is None:
                raise ReassessmentError("PROVIDER_RESULT_NOT_FOUND")
            referral = await self._referrals.get(provider_result.referral_id)
            if referral is None or referral.intervention_id != intervention_id:
                raise ReassessmentError("PROVIDER_RESULT_INTERVENTION_MISMATCH")

        now = datetime.now(UTC)
        assessment = Assessment(
            id=uuid4(),
            household_id=household_id,
            assessment_type=assessment_type,
            definition_version_id=definition_version_id,
            status=AssessmentStatus.IN_PROGRESS,
            version=1,
            started_at=now,
            started_by=actor_id,
            reason=reason.strip(),
            intervention_id=intervention_id,
            provider_result_id=provider_result_id,
            parent_assessment_id=parent_assessment_id,
        )
        await self._assessments.add(assessment)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="ReassessmentStarted",
                event_version=1,
                aggregate_type="ASSESSMENT",
                aggregate_id=assessment.id,
                aggregate_version=assessment.version,
                actor_id=actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=correlation_id,
                causation_id=None,
                payload={
                    "assessment_id": str(assessment.id),
                    "household_id": str(household_id),
                    "assessment_type": assessment.assessment_type.value,
                    "intervention_id": str(intervention_id),
                    "provider_result_id": (
                        None if provider_result_id is None else str(provider_result_id)
                    ),
                    "parent_assessment_id": (
                        None if parent_assessment_id is None else str(parent_assessment_id)
                    ),
                    "definition_version_id": str(definition_version_id),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=actor_id,
                action="assessment.reassessment.start",
                resource_type="ASSESSMENT",
                resource_id=assessment.id,
                request_id=request_id,
                correlation_id=correlation_id,
                created_at=now,
                purpose="OUTCOME_MEASUREMENT",
                metadata={
                    "event_id": str(event_id),
                    "intervention_id": str(intervention_id),
                    "provider_result_id": (
                        None if provider_result_id is None else str(provider_result_id)
                    ),
                },
            )
        )
        return assessment
