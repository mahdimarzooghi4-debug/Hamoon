from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.family_data.infrastructure.repositories import (
    SqlAlchemyAcceptedStateRepository,
)
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.provider.api.schemas import (
    MatchProvidersRequest,
    ProviderData,
    ProviderListResponse,
    ProviderMatchCandidateData,
    ProviderMatchData,
    ProviderMatchResponse,
    ProviderResponse,
    ProviderServiceData,
    ProviderServiceListResponse,
    ProviderServiceResponse,
)
from hamoon.domains.provider.application.commands import MatchProvidersCommand
from hamoon.domains.provider.application.matching import MatchProvidersHandler
from hamoon.domains.provider.domain.entities import ProviderService
from hamoon.domains.provider.domain.errors import ProviderMatchError
from hamoon.domains.provider.infrastructure.repositories import (
    SqlAlchemyProviderMatchRepository,
    SqlAlchemyProviderRegistryRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["provider"])


def _provider_data(item) -> ProviderData:
    return ProviderData(
        id=item.id,
        code=item.code,
        name=item.name,
        status=item.status,
        organization_type=item.organization_type,
        integration_mode=item.integration_mode,
        created_at=item.created_at,
    )


async def _service_data(
    *,
    service: ProviderService,
    registry: SqlAlchemyProviderRegistryRepository,
) -> ProviderServiceData:
    capacity = await registry.latest_capacity(service.id)
    from hamoon.domains.provider.domain.entities import CapacityStatus

    return ProviderServiceData(
        id=service.id,
        provider_id=service.provider_id,
        service_type=service.service_type,
        title=service.title,
        description=service.description,
        supported_intervention_types=[
            item.value for item in service.supported_intervention_types
        ],
        eligibility_policy_version=service.eligibility_policy_version,
        coverage_policy_version=service.coverage_policy_version,
        coverage_fact_type=service.coverage_fact_type,
        coverage_codes=list(service.coverage_codes),
        sla_policy_version=service.sla_policy_version,
        active=service.active,
        capacity_status=(
            CapacityStatus.UNKNOWN if capacity is None else capacity.capacity_status
        ),
        available_slots=None if capacity is None else capacity.available_slots,
    )


@router.get("/api/v1/providers", response_model=ProviderListResponse)
async def list_providers(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderListResponse:
    items = await SqlAlchemyProviderRegistryRepository(session).list_providers()
    return ProviderListResponse(data=[_provider_data(item) for item in items])


@router.get("/api/v1/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: UUID,
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderResponse:
    item = await SqlAlchemyProviderRegistryRepository(session).get_provider(provider_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    return ProviderResponse(data=_provider_data(item))


@router.get(
    "/api/v1/providers/{provider_id}/services",
    response_model=ProviderServiceListResponse,
)
async def list_provider_services(
    provider_id: UUID,
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderServiceListResponse:
    registry = SqlAlchemyProviderRegistryRepository(session)
    services = await registry.list_services_for_provider(provider_id)
    return ProviderServiceListResponse(
        data=[
            await _service_data(service=service, registry=registry)
            for service in services
        ]
    )


@router.get(
    "/api/v1/provider-services/{service_id}",
    response_model=ProviderServiceResponse,
)
async def get_provider_service(
    service_id: UUID,
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderServiceResponse:
    registry = SqlAlchemyProviderRegistryRepository(session)
    service = await registry.get_service(service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    return ProviderServiceResponse(
        data=await _service_data(service=service, registry=registry)
    )


@router.post(
    "/api/v1/interventions/{intervention_id}/match-providers",
    response_model=ProviderMatchResponse,
)
async def match_providers(
    intervention_id: UUID,
    body: MatchProvidersRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderMatchResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    interventions = SqlAlchemyInterventionRepository(session)

    try:
        async with session.begin():
            intervention = await interventions.get(intervention_id)
            if intervention is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "RESOURCE_NOT_FOUND"},
                )
            await require_household_assignment(
                session=session,
                context=context,
                household_id=intervention.household_id,
            )
            match = await MatchProvidersHandler(
                interventions=interventions,
                accepted_state=SqlAlchemyAcceptedStateRepository(session),
                registry=SqlAlchemyProviderRegistryRepository(session),
                matches=SqlAlchemyProviderMatchRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                MatchProvidersCommand(
                    intervention_id=intervention_id,
                    service_type=body.service_type,
                    household_context_version=body.household_context_version,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except ProviderMatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return ProviderMatchResponse(
        data=ProviderMatchData(
            provider_match_id=match.id,
            intervention_id=match.intervention_id,
            service_type=match.service_type,
            household_context_version=match.household_context_version,
            matching_policy_version=match.matching_policy_version,
            generated_at=match.generated_at,
            candidates=[
                ProviderMatchCandidateData(
                    provider_id=item.provider_id,
                    provider_service_id=item.provider_service_id,
                    eligibility=item.eligibility,
                    capacity_status=item.capacity_status,
                    reasons=list(item.reasons),
                )
                for item in match.candidates
            ],
        )
    )
