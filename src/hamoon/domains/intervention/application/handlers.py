from datetime import UTC, datetime
from uuid import uuid4

from hamoon.domains.intelligence.ports.repositories import DecisionTraceRepository
from hamoon.domains.intervention.application.commands import ActivateInterventionCommand
from hamoon.domains.intervention.domain.entities import (
    Intervention,
    InterventionStatus,
)
from hamoon.domains.intervention.domain.errors import InterventionActivationError
from hamoon.domains.intervention.ports.repositories import InterventionRepository
from hamoon.domains.prescription.domain.entities import (
    PrescriptionItemStatus,
    PrescriptionStatus,
)
from hamoon.domains.prescription.ports.repositories import PrescriptionRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


class ActivateInterventionHandler:
    def __init__(
        self,
        *,
        prescriptions: PrescriptionRepository,
        interventions: InterventionRepository,
        traces: DecisionTraceRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._prescriptions = prescriptions
        self._interventions = interventions
        self._traces = traces
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: ActivateInterventionCommand,
    ) -> Intervention:
        prescription = await self._prescriptions.get(command.prescription_id)
        if prescription is None:
            raise InterventionActivationError("PRESCRIPTION_NOT_FOUND")
        if prescription.status not in {
            PrescriptionStatus.APPROVED,
            PrescriptionStatus.MODIFIED,
            PrescriptionStatus.REPLACED,
        }:
            raise InterventionActivationError("PRESCRIPTION_NOT_ACCEPTED")

        item = await self._prescriptions.get_item(
            prescription_id=prescription.id,
            item_id=command.prescription_item_id,
        )
        if item is None:
            raise InterventionActivationError("PRESCRIPTION_ITEM_NOT_FOUND")
        if item.status is not PrescriptionItemStatus.ACCEPTED:
            raise InterventionActivationError("PRESCRIPTION_ITEM_NOT_ACCEPTED")
        if await self._interventions.get_by_prescription_item(item.id) is not None:
            raise InterventionActivationError("INTERVENTION_ALREADY_EXISTS")

        now = datetime.now(UTC)
        intervention = Intervention(
            id=uuid4(),
            household_id=prescription.household_id,
            prescription_item_id=item.id,
            intervention_type=item.intervention_type,
            target_pgor_variable=item.target_pgor_variable,
            status=InterventionStatus.ACTIVE,
            started_at=now,
            completed_at=None,
            owner_actor_id=command.actor_id,
        )
        await self._interventions.add(intervention)
        await self._prescriptions.mark_item_activated(item.id)
        await self._traces.attach_intervention(
            ai_decision_id=prescription.ai_decision_id,
            intervention_id=intervention.id,
        )

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="InterventionActivated",
                event_version=1,
                aggregate_type="INTERVENTION",
                aggregate_id=intervention.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "intervention_id": str(intervention.id),
                    "household_id": str(intervention.household_id),
                    "prescription_id": str(prescription.id),
                    "prescription_item_id": str(item.id),
                    "intervention_type": intervention.intervention_type.value,
                    "target_pgor_variable": intervention.target_pgor_variable.value,
                    "status": intervention.status.value,
                    "started_at": now.isoformat(),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="intervention.activate",
                resource_type="INTERVENTION",
                resource_id=intervention.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="EMPOWERMENT_INTERVENTION",
                metadata={
                    "event_id": str(event_id),
                    "prescription_id": str(prescription.id),
                    "prescription_item_id": str(item.id),
                    "target_pgor_variable": intervention.target_pgor_variable.value,
                },
            )
        )
        return intervention
