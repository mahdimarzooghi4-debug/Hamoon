from datetime import UTC, datetime
from uuid import uuid4

from hamoon.domains.family_data.ports.repositories import (
    AcceptedStateRepository,
    HouseholdFactRepository,
)
from hamoon.domains.intelligence.domain.decisions import (
    HumanDecision,
    HumanDecisionAction,
    HumanDecisionContext,
    LearningSignal,
    LearningSignalQuality,
    LearningSignalType,
)
from hamoon.domains.intelligence.ports.repositories import (
    DecisionTraceRepository,
    HumanDecisionRepository,
    LearningSignalRepository,
)
from hamoon.domains.intervention.ports.repositories import InterventionRepository
from hamoon.domains.provider.domain.entities import MatchEligibility, ProviderSelection
from hamoon.domains.provider.ports.repositories import (
    ProviderMatchRepository,
    ProviderRegistryRepository,
    ProviderSelectionRepository,
)
from hamoon.domains.referral.application.commands import CreateReferralCommand
from hamoon.domains.referral.domain.entities import (
    Referral,
    ReferralDataItem,
    ReferralStatus,
)
from hamoon.domains.referral.domain.errors import ReferralCreationError
from hamoon.domains.referral.ports.repositories import ReferralRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


class CreateReferralHandler:
    def __init__(
        self,
        *,
        interventions: InterventionRepository,
        registry: ProviderRegistryRepository,
        matches: ProviderMatchRepository,
        selections: ProviderSelectionRepository,
        referrals: ReferralRepository,
        facts: HouseholdFactRepository,
        accepted_state: AcceptedStateRepository,
        human_decisions: HumanDecisionRepository,
        learning_signals: LearningSignalRepository,
        traces: DecisionTraceRepository | None = None,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._interventions = interventions
        self._registry = registry
        self._matches = matches
        self._selections = selections
        self._referrals = referrals
        self._facts = facts
        self._accepted_state = accepted_state
        self._human_decisions = human_decisions
        self._learning_signals = learning_signals
        self._traces = traces
        self._events = events
        self._audits = audits

    async def handle(self, command: CreateReferralCommand) -> tuple[Referral, ProviderSelection, HumanDecision, LearningSignal]:
        intervention = await self._interventions.get(command.intervention_id)
        if intervention is None:
            raise ReferralCreationError("INTERVENTION_NOT_FOUND")
        provider = await self._registry.get_provider(command.provider_id)
        service = await self._registry.get_service(command.provider_service_id)
        if provider is None or provider.status.value != "ACTIVE":
            raise ReferralCreationError("PROVIDER_NOT_ACTIVE")
        if (
            service is None
            or not service.active
            or service.provider_id != provider.id
        ):
            raise ReferralCreationError("PROVIDER_SERVICE_NOT_ACTIVE")

        match = await self._matches.get_latest_for_intervention(intervention.id)
        if match is None:
            raise ReferralCreationError("PROVIDER_MATCH_REQUIRED")
        candidate = await self._matches.get_candidate(
            provider_match_id=match.id,
            provider_id=provider.id,
            provider_service_id=service.id,
        )
        if candidate is None or candidate.eligibility is not MatchEligibility.ELIGIBLE:
            raise ReferralCreationError("PROVIDER_NOT_ELIGIBLE_IN_LATEST_MATCH")

        accepted = await self._accepted_state.list_for_household(
            intervention.household_id
        )
        accepted_fact_ids = {item.fact_id for item in accepted}

        referral_id = uuid4()
        now = datetime.now(UTC)
        data_items: list[ReferralDataItem] = []
        seen_fact_ids: set[object] = set()
        for item in command.shared_data_items:
            if item.source_fact_id in seen_fact_ids:
                raise ReferralCreationError("DUPLICATE_SHARED_FACT")
            seen_fact_ids.add(item.source_fact_id)
            if item.source_fact_id not in accepted_fact_ids:
                raise ReferralCreationError("SHARED_FACT_NOT_CURRENT_ACCEPTED")
            fact = await self._facts.get_for_household(
                household_id=intervention.household_id,
                fact_id=item.source_fact_id,
            )
            if fact is None:
                raise ReferralCreationError("SHARED_FACT_NOT_FOUND")
            if not item.purpose.strip():
                raise ReferralCreationError("SHARING_PURPOSE_REQUIRED")
            data_items.append(
                ReferralDataItem(
                    id=uuid4(),
                    referral_id=referral_id,
                    data_category=fact.fact_type,
                    source_fact_id=fact.id,
                    snapshot_value=fact.value,
                    purpose=item.purpose,
                    authorization_basis=None,
                    shared_at=None,
                )
            )

        human_decision = HumanDecision(
            id=uuid4(),
            household_id=intervention.household_id,
            ai_decision_id=None,
            actor_id=command.actor_id,
            action=HumanDecisionAction.CONFIRM,
            reason_code="CASEWORKER_PROVIDER_SELECTION",
            reason_text=None,
            accepted_payload={
                "provider_match_id": str(match.id),
                "provider_id": str(provider.id),
                "provider_service_id": str(service.id),
            },
            modified_payload=None,
            decided_at=now,
            decision_context=HumanDecisionContext.PROVIDER_MATCH,
            provider_match_id=match.id,
        )
        selection = ProviderSelection(
            id=uuid4(),
            provider_match_id=match.id,
            intervention_id=intervention.id,
            provider_id=provider.id,
            provider_service_id=service.id,
            human_decision_id=human_decision.id,
            selected_by=command.actor_id,
            selected_at=now,
        )
        referral = Referral(
            id=referral_id,
            household_id=intervention.household_id,
            intervention_id=intervention.id,
            provider_match_id=match.id,
            provider_selection_id=selection.id,
            provider_id=provider.id,
            provider_service_id=service.id,
            status=ReferralStatus.READY,
            priority=command.priority,
            version=1,
            response_due_at=command.response_due_at,
            sent_at=None,
            accepted_at=None,
            completed_at=None,
            cancelled_at=None,
            external_referral_id=None,
            subject_reference=None,
            created_by=command.actor_id,
            created_at=now,
            data_items=tuple(data_items),
        )
        signal = LearningSignal(
            id=uuid4(),
            household_id=intervention.household_id,
            signal_type=LearningSignalType.PROVIDER_SELECTED,
            ai_decision_id=None,
            human_decision_id=human_decision.id,
            diagnosis_id=None,
            signal_label="PROVIDER_SELECTED",
            quality_status=LearningSignalQuality.RAW,
            created_at=now,
            created_by=command.actor_id,
            intervention_id=intervention.id,
            provider_match_id=match.id,
            provider_id=provider.id,
        )

        await self._human_decisions.add(human_decision)
        await self._selections.add(selection)
        await self._referrals.add(referral)
        await self._learning_signals.add(signal)
        if self._traces is not None:
            await self._traces.attach_referral(
                intervention_id=intervention.id,
                referral_id=referral.id,
            )

        selection_event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=selection_event_id,
                event_type="ProviderSelectedByHuman",
                event_version=1,
                aggregate_type="PROVIDER_SELECTION",
                aggregate_id=selection.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "provider_match_id": str(match.id),
                    "intervention_id": str(intervention.id),
                    "provider_id": str(provider.id),
                    "provider_service_id": str(service.id),
                    "human_decision_id": str(human_decision.id),
                },
            )
        )
        await self._events.record(
            DomainEventRecord(
                event_id=uuid4(),
                event_type="ReferralCreated",
                event_version=1,
                aggregate_type="REFERRAL",
                aggregate_id=referral.id,
                aggregate_version=referral.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=str(selection_event_id),
                payload={
                    "referral_id": str(referral.id),
                    "intervention_id": str(intervention.id),
                    "provider_id": str(provider.id),
                    "provider_service_id": str(service.id),
                    "status": referral.status.value,
                    "shared_data_item_ids": [str(item.id) for item in data_items],
                },
            )
        )
        await self._events.record(
            DomainEventRecord(
                event_id=uuid4(),
                event_type="LearningSignalCreated",
                event_version=1,
                aggregate_type="LEARNING_SIGNAL",
                aggregate_id=signal.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=str(selection_event_id),
                payload={
                    "learning_signal_id": str(signal.id),
                    "household_id": str(signal.household_id),
                    "signal_type": signal.signal_type.value,
                    "human_decision_id": str(signal.human_decision_id),
                    "intervention_id": str(intervention.id),
                    "provider_id": str(provider.id),
                    "quality_status": signal.quality_status.value,
                },
            )
        )

        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="provider.select",
                resource_type="INTERVENTION",
                resource_id=intervention.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="SERVICE_MATCHING",
                metadata={
                    "provider_match_id": str(match.id),
                    "provider_id": str(provider.id),
                    "provider_service_id": str(service.id),
                    "human_decision_id": str(human_decision.id),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="referral.create",
                resource_type="REFERRAL",
                resource_id=referral.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="SERVICE_DELIVERY",
                metadata={
                    "provider_selection_id": str(selection.id),
                    "shared_data_item_count": len(data_items),
                    "status": referral.status.value,
                },
            )
        )
        return referral, selection, human_decision, signal
