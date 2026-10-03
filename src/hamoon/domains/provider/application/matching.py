from datetime import UTC, datetime
from uuid import uuid4

from hamoon.domains.family_data.domain.entities import CurrentAcceptedFact
from hamoon.domains.family_data.ports.repositories import AcceptedStateRepository
from hamoon.domains.intervention.ports.repositories import InterventionRepository
from hamoon.domains.provider.application.commands import MatchProvidersCommand
from hamoon.domains.provider.domain.entities import (
    CapacityStatus,
    EligibilityOperator,
    MatchEligibility,
    ProviderEligibilityRule,
    ProviderMatch,
    ProviderMatchCandidate,
)
from hamoon.domains.provider.domain.errors import ProviderMatchError
from hamoon.domains.provider.ports.repositories import (
    ProviderMatchRepository,
    ProviderRegistryRepository,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder

MATCHING_POLICY_VERSION = "provider-match-rules-v1"


def _rule_matches(
    *,
    rule: ProviderEligibilityRule,
    accepted: dict[str, CurrentAcceptedFact],
) -> bool:
    fact = accepted.get(rule.fact_type)
    if rule.operator is EligibilityOperator.EXISTS:
        return fact is not None
    if fact is None:
        return False
    if rule.operator is EligibilityOperator.EQUALS:
        return fact.accepted_value == rule.expected_value
    if rule.operator is EligibilityOperator.IN:
        values = rule.expected_value
        return isinstance(values, list) and fact.accepted_value in values
    return False


class MatchProvidersHandler:
    def __init__(
        self,
        *,
        interventions: InterventionRepository,
        accepted_state: AcceptedStateRepository,
        registry: ProviderRegistryRepository,
        matches: ProviderMatchRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._interventions = interventions
        self._accepted_state = accepted_state
        self._registry = registry
        self._matches = matches
        self._events = events
        self._audits = audits

    async def handle(self, command: MatchProvidersCommand) -> ProviderMatch:
        intervention = await self._interventions.get(command.intervention_id)
        if intervention is None:
            raise ProviderMatchError("INTERVENTION_NOT_FOUND")
        if not command.service_type.strip():
            raise ProviderMatchError("SERVICE_TYPE_REQUIRED")
        if command.household_context_version < 1:
            raise ProviderMatchError("HOUSEHOLD_CONTEXT_VERSION_INVALID")

        accepted_items = await self._accepted_state.list_for_household(
            intervention.household_id
        )
        accepted = {item.fact_type: item for item in accepted_items}
        services = await self._registry.list_services_by_type(command.service_type)

        match_id = uuid4()
        candidates: list[ProviderMatchCandidate] = []
        for service in services:
            provider = await self._registry.get_provider(service.provider_id)
            if provider is None or provider.status.value != "ACTIVE" or not service.active:
                continue

            reasons: list[str] = []
            if intervention.intervention_type not in service.supported_intervention_types:
                reasons.append("INTERVENTION_TYPE_NOT_SUPPORTED")

            if service.coverage_codes:
                if service.coverage_fact_type is None:
                    reasons.append("COVERAGE_POLICY_CONTEXT_MISSING")
                else:
                    coverage_fact = accepted.get(service.coverage_fact_type)
                    coverage_value = (
                        coverage_fact.accepted_value
                        if coverage_fact is not None
                        else None
                    )
                    if not isinstance(coverage_value, str):
                        reasons.append("COVERAGE_CONTEXT_MISSING")
                    elif coverage_value not in service.coverage_codes:
                        reasons.append("OUTSIDE_SERVICE_COVERAGE")

            for rule in await self._registry.list_eligibility_rules(service.id):
                if rule.active and not _rule_matches(rule=rule, accepted=accepted):
                    reasons.append(rule.reason_code)

            capacity = await self._registry.latest_capacity(service.id)
            capacity_status = (
                CapacityStatus.UNKNOWN
                if capacity is None
                else capacity.capacity_status
            )
            if capacity is None:
                reasons.append("CAPACITY_UNKNOWN")
            elif capacity.capacity_status is not CapacityStatus.AVAILABLE:
                reasons.append(f"CAPACITY_{capacity.capacity_status.value}")
            elif capacity.available_slots is not None and capacity.available_slots <= 0:
                reasons.append("CAPACITY_FULL")
                capacity_status = CapacityStatus.FULL

            candidates.append(
                ProviderMatchCandidate(
                    id=uuid4(),
                    provider_match_id=match_id,
                    provider_id=provider.id,
                    provider_service_id=service.id,
                    eligibility=(
                        MatchEligibility.ELIGIBLE
                        if not reasons
                        else MatchEligibility.INELIGIBLE
                    ),
                    capacity_status=capacity_status,
                    reasons=tuple(dict.fromkeys(reasons)),
                )
            )

        now = datetime.now(UTC)
        match = ProviderMatch(
            id=match_id,
            household_id=intervention.household_id,
            intervention_id=intervention.id,
            service_type=command.service_type,
            household_context_version=command.household_context_version,
            matching_policy_version=MATCHING_POLICY_VERSION,
            generated_at=now,
            generated_by=command.actor_id,
            candidates=tuple(candidates),
        )
        await self._matches.add(match)

        eligible_provider_ids = [
            str(item.provider_id)
            for item in candidates
            if item.eligibility is MatchEligibility.ELIGIBLE
        ]
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="ProviderMatchGenerated",
                event_version=1,
                aggregate_type="PROVIDER_MATCH",
                aggregate_id=match.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "provider_match_id": str(match.id),
                    "intervention_id": str(intervention.id),
                    "service_type": match.service_type,
                    "matching_policy_version": match.matching_policy_version,
                    "candidate_count": len(eligible_provider_ids),
                    "candidate_provider_ids": eligible_provider_ids,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="provider.match.generate",
                resource_type="INTERVENTION",
                resource_id=intervention.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="PROVIDER_MATCHING",
                metadata={
                    "event_id": str(event_id),
                    "provider_match_id": str(match.id),
                    "matching_policy_version": match.matching_policy_version,
                    "eligible_candidate_count": len(eligible_provider_ids),
                },
            )
        )
        return match
