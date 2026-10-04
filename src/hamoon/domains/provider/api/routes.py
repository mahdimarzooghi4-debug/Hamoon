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
    ProviderMatchContextData,
    ProviderMatchContextFactData,
    ProviderMatchContextResponse,
    ProviderMatchData,
    ProviderMatchResponse,
    ProviderMatchServiceTypeData,
    ProviderResponse,
    ProviderServiceData,
    ProviderServiceListResponse,
    ProviderServiceResponse,
)
from hamoon.domains.provider.application.commands import MatchProvidersCommand
from hamoon.domains.provider.application.matching import MatchProvidersHandler
from hamoon.domains.provider.domain.entities import (
    CapacityStatus,
    Provider,
    ProviderMatch,
    ProviderService,
)
from hamoon.domains.provider.domain.errors import ProviderMatchError
from hamoon.domains.provider.infrastructure.repositories import (
    SqlAlchemyProviderMatchRepository,
    SqlAlchemyProviderRegistryRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["provider"])


def _provider_data(item: Provider) -> ProviderData:
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


async def _provider_match_data(
    *,
    match: ProviderMatch,
    registry: SqlAlchemyProviderRegistryRepository,
) -> ProviderMatchData:
    candidates: list[ProviderMatchCandidateData] = []
    for item in match.candidates:
        provider = await registry.get_provider(item.provider_id)
        service = await registry.get_service(item.provider_service_id)
        if provider is None or service is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "PROVIDER_MATCH_REFERENCE_MISSING"},
            )
        candidates.append(
            ProviderMatchCandidateData(
                provider_id=item.provider_id,
                provider_name=provider.name,
                provider_service_id=item.provider_service_id,
                service_title=service.title,
                eligibility=item.eligibility,
                capacity_status=item.capacity_status,
                reasons=list(item.reasons),
            )
        )
    return ProviderMatchData(
        provider_match_id=match.id,
        intervention_id=match.intervention_id,
        service_type=match.service_type,
        household_context_version=match.household_context_version,
        matching_policy_version=match.matching_policy_version,
        generated_at=match.generated_at,
        candidates=candidates,
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


@router.get(
    "/api/v1/interventions/{intervention_id}/provider-match-context",
    response_model=ProviderMatchContextResponse,
)
async def get_provider_match_context(
    intervention_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderMatchContextResponse:
    intervention = await SqlAlchemyInterventionRepository(session).get(intervention_id)
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

    accepted_state = SqlAlchemyAcceptedStateRepository(session)
    accepted = await accepted_state.list_for_household(intervention.household_id)
    context_version = await accepted_state.context_version(intervention.household_id)

    registry = SqlAlchemyProviderRegistryRepository(session)
    active_services = await registry.list_active_services()
    compatible = [
        item
        for item in active_services
        if intervention.intervention_type in item.supported_intervention_types
    ]
    grouped: dict[str, list[str]] = {}
    for item in compatible:
        grouped.setdefault(item.service_type, []).append(item.title)

    return ProviderMatchContextResponse(
        data=ProviderMatchContextData(
            intervention_id=intervention.id,
            intervention_type=intervention.intervention_type.value,
            target_pgor_variable=intervention.target_pgor_variable.value,
            household_context_version=context_version,
            service_types=[
                ProviderMatchServiceTypeData(
                    service_type=service_type,
                    service_titles=list(dict.fromkeys(titles)),
                    active_service_count=len(titles),
                )
                for service_type, titles in grouped.items()
            ],
            shareable_facts=[
                ProviderMatchContextFactData(
                    fact_id=item.fact_id,
                    fact_type=item.fact_type,
                    projection_version=item.projection_version,
                    effective_from=item.effective_from,
                )
                for item in accepted
            ],
        )
    )


@router.get(
    "/api/v1/interventions/{intervention_id}/provider-match",
    response_model=ProviderMatchResponse,
)
async def get_latest_provider_match(
    intervention_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderMatchResponse:
    interventions = SqlAlchemyInterventionRepository(session)
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
    match = await SqlAlchemyProviderMatchRepository(
        session
    ).get_latest_for_intervention(intervention_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROVIDER_MATCH_NOT_FOUND"},
        )
    registry = SqlAlchemyProviderRegistryRepository(session)
    return ProviderMatchResponse(
        data=await _provider_match_data(
            match=match,
            registry=registry,
        )
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
            accepted_state = SqlAlchemyAcceptedStateRepository(session)
            current_context_version = await accepted_state.context_version(
                intervention.household_id
            )
            if current_context_version < 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"code": "ACCEPTED_STATE_REQUIRED"},
                )
            if body.household_context_version != current_context_version:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "HOUSEHOLD_CONTEXT_VERSION_CONFLICT",
                        "current_version": current_context_version,
                    },
                )
            registry = SqlAlchemyProviderRegistryRepository(session)
            match = await MatchProvidersHandler(
                interventions=interventions,
                accepted_state=accepted_state,
                registry=registry,
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
            response_data = await _provider_match_data(
                match=match,
                registry=registry,
            )
    except ProviderMatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return ProviderMatchResponse(data=response_data)
