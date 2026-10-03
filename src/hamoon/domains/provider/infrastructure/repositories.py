from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.provider.domain.entities import (
    CapacityStatus,
    Provider,
    ProviderCapacitySnapshot,
    ProviderEligibilityRule,
    ProviderMatch,
    ProviderMatchCandidate,
    ProviderSelection,
    ProviderService,
)
from hamoon.domains.provider.infrastructure.models import (
    ProviderCapacitySnapshotModel,
    ProviderMatchCandidateModel,
    ProviderMatchModel,
    ProviderModel,
    ProviderSelectionModel,
    ProviderServiceEligibilityRuleModel,
    ProviderServiceModel,
)


def _provider(model: ProviderModel) -> Provider:
    return Provider(
        id=model.id,
        code=model.code,
        name=model.name,
        status=model.status,
        organization_type=model.organization_type,
        integration_mode=model.integration_mode,
        created_at=model.created_at,
    )


def _service(model: ProviderServiceModel) -> ProviderService:
    return ProviderService(
        id=model.id,
        provider_id=model.provider_id,
        service_type=model.service_type,
        title=model.title,
        description=model.description,
        supported_intervention_types=tuple(
            InterventionType(value) for value in model.supported_intervention_types
        ),
        eligibility_policy_version=model.eligibility_policy_version,
        coverage_policy_version=model.coverage_policy_version,
        coverage_fact_type=model.coverage_fact_type,
        coverage_codes=tuple(model.coverage_codes),
        sla_policy_version=model.sla_policy_version,
        active=model.active,
    )


def _capacity(model: ProviderCapacitySnapshotModel) -> ProviderCapacitySnapshot:
    return ProviderCapacitySnapshot(
        id=model.id,
        provider_service_id=model.provider_service_id,
        capacity_status=model.capacity_status,
        available_slots=model.available_slots,
        valid_at=model.valid_at,
        received_at=model.received_at,
        source_reference=model.source_reference,
    )


def _candidate(model: ProviderMatchCandidateModel) -> ProviderMatchCandidate:
    return ProviderMatchCandidate(
        id=model.id,
        provider_match_id=model.provider_match_id,
        provider_id=model.provider_id,
        provider_service_id=model.provider_service_id,
        eligibility=model.eligibility,
        capacity_status=model.capacity_status,
        reasons=tuple(model.reasons),
    )


class SqlAlchemyProviderRegistryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_provider(self, provider_id: UUID) -> Provider | None:
        model = await self._session.get(ProviderModel, provider_id)
        return None if model is None else _provider(model)

    async def list_providers(self) -> list[Provider]:
        result = await self._session.execute(
            select(ProviderModel).order_by(ProviderModel.name)
        )
        return [_provider(model) for model in result.scalars().all()]

    async def get_service(self, service_id: UUID) -> ProviderService | None:
        model = await self._session.get(ProviderServiceModel, service_id)
        return None if model is None else _service(model)

    async def list_services_for_provider(
        self,
        provider_id: UUID,
    ) -> list[ProviderService]:
        result = await self._session.execute(
            select(ProviderServiceModel)
            .where(ProviderServiceModel.provider_id == provider_id)
            .order_by(ProviderServiceModel.title)
        )
        return [_service(model) for model in result.scalars().all()]

    async def list_services_by_type(
        self,
        service_type: str,
    ) -> list[ProviderService]:
        result = await self._session.execute(
            select(ProviderServiceModel)
            .where(
                ProviderServiceModel.service_type == service_type,
                ProviderServiceModel.active.is_(True),
            )
            .order_by(ProviderServiceModel.title)
        )
        return [_service(model) for model in result.scalars().all()]

    async def list_eligibility_rules(
        self,
        provider_service_id: UUID,
    ) -> list[ProviderEligibilityRule]:
        result = await self._session.execute(
            select(ProviderServiceEligibilityRuleModel)
            .where(
                ProviderServiceEligibilityRuleModel.provider_service_id
                == provider_service_id,
                ProviderServiceEligibilityRuleModel.active.is_(True),
            )
            .order_by(ProviderServiceEligibilityRuleModel.fact_type)
        )
        return [
            ProviderEligibilityRule(
                id=model.id,
                provider_service_id=model.provider_service_id,
                fact_type=model.fact_type,
                operator=model.operator,
                expected_value=model.expected_value,
                reason_code=model.reason_code,
                active=model.active,
            )
            for model in result.scalars().all()
        ]

    async def latest_capacity(
        self,
        provider_service_id: UUID,
    ) -> ProviderCapacitySnapshot | None:
        result = await self._session.execute(
            select(ProviderCapacitySnapshotModel)
            .where(
                ProviderCapacitySnapshotModel.provider_service_id
                == provider_service_id
            )
            .order_by(
                desc(ProviderCapacitySnapshotModel.valid_at),
                desc(ProviderCapacitySnapshotModel.received_at),
            )
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else _capacity(model)


class SqlAlchemyProviderMatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, match: ProviderMatch) -> None:
        self._session.add(
            ProviderMatchModel(
                id=match.id,
                household_id=match.household_id,
                intervention_id=match.intervention_id,
                service_type=match.service_type,
                household_context_version=match.household_context_version,
                matching_policy_version=match.matching_policy_version,
                generated_at=match.generated_at,
                generated_by=match.generated_by,
            )
        )
        for candidate in match.candidates:
            self._session.add(
                ProviderMatchCandidateModel(
                    id=candidate.id,
                    provider_match_id=match.id,
                    provider_id=candidate.provider_id,
                    provider_service_id=candidate.provider_service_id,
                    eligibility=candidate.eligibility,
                    capacity_status=candidate.capacity_status,
                    reasons=list(candidate.reasons),
                )
            )

    async def _hydrate(self, model: ProviderMatchModel) -> ProviderMatch:
        result = await self._session.execute(
            select(ProviderMatchCandidateModel)
            .where(ProviderMatchCandidateModel.provider_match_id == model.id)
            .order_by(ProviderMatchCandidateModel.provider_service_id)
        )
        return ProviderMatch(
            id=model.id,
            household_id=model.household_id,
            intervention_id=model.intervention_id,
            service_type=model.service_type,
            household_context_version=model.household_context_version,
            matching_policy_version=model.matching_policy_version,
            generated_at=model.generated_at,
            generated_by=model.generated_by,
            candidates=tuple(_candidate(item) for item in result.scalars().all()),
        )

    async def get(self, match_id: UUID) -> ProviderMatch | None:
        model = await self._session.get(ProviderMatchModel, match_id)
        return None if model is None else await self._hydrate(model)

    async def get_latest_for_intervention(
        self,
        intervention_id: UUID,
    ) -> ProviderMatch | None:
        result = await self._session.execute(
            select(ProviderMatchModel)
            .where(ProviderMatchModel.intervention_id == intervention_id)
            .order_by(desc(ProviderMatchModel.generated_at))
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else await self._hydrate(model)

    async def get_candidate(
        self,
        *,
        provider_match_id: UUID,
        provider_id: UUID,
        provider_service_id: UUID,
    ) -> ProviderMatchCandidate | None:
        result = await self._session.execute(
            select(ProviderMatchCandidateModel).where(
                ProviderMatchCandidateModel.provider_match_id == provider_match_id,
                ProviderMatchCandidateModel.provider_id == provider_id,
                ProviderMatchCandidateModel.provider_service_id
                == provider_service_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _candidate(model)


class SqlAlchemyProviderSelectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, selection: ProviderSelection) -> None:
        self._session.add(
            ProviderSelectionModel(
                id=selection.id,
                provider_match_id=selection.provider_match_id,
                intervention_id=selection.intervention_id,
                provider_id=selection.provider_id,
                provider_service_id=selection.provider_service_id,
                human_decision_id=selection.human_decision_id,
                selected_by=selection.selected_by,
                selected_at=selection.selected_at,
            )
        )
