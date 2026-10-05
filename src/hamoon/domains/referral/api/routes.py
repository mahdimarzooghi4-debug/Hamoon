from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.config.settings import get_settings
from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import (
    get_provider_authorization_context,
    require_roles,
)
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.family_data.infrastructure.repositories import (
    SqlAlchemyAcceptedStateRepository,
    SqlAlchemyHouseholdFactRepository,
)
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyDecisionTraceRepository,
    SqlAlchemyHumanDecisionRepository,
    SqlAlchemyLearningSignalRepository,
)
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.provider.infrastructure.repositories import (
    SqlAlchemyProviderMatchRepository,
    SqlAlchemyProviderRegistryRepository,
    SqlAlchemyProviderSelectionRepository,
)
from hamoon.domains.referral.api.schemas import (
    CreateReferralRequest,
    ProviderCallbackData,
    ProviderCallbackResponse,
    ProviderStatusCallbackRequest,
    ReferralData,
    ReferralDataItemData,
    ReferralEventData,
    ReferralResponse,
    ReferralTimelineResponse,
    SendReferralData,
    SendReferralRequest,
    SendReferralResponse,
    TransitionReferralRequest,
)
from hamoon.domains.referral.application.commands import (
    CreateReferralCommand,
    ProviderStatusCallbackCommand,
    SendReferralCommand,
    SharedFactInput,
    TransitionReferralCommand,
)
from hamoon.domains.referral.application.handlers import CreateReferralHandler
from hamoon.domains.referral.application.lifecycle import (
    ProviderStatusCallbackHandler,
    SendReferralHandler,
    TransitionReferralHandler,
)
from hamoon.domains.referral.domain.entities import Referral, ReferralStatus
from hamoon.domains.referral.domain.errors import (
    ReferralCreationError,
    ReferralIdempotencyConflictError,
    ReferralProviderScopeError,
    ReferralTransitionError,
    ReferralVersionConflictError,
)
from hamoon.domains.referral.infrastructure.repositories import (
    SqlAlchemyProviderCallbackInboxRepository,
    SqlAlchemyReferralDispatchRepository,
    SqlAlchemyReferralRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder
from hamoon.infrastructure.temporal.referral_starter import (
    signal_referral_cancelled_best_effort,
    signal_referral_provider_status_best_effort,
    start_referral_workflow_best_effort,
)

router = APIRouter(tags=["referral"])


async def _data(
    item: Referral,
    *,
    registry: SqlAlchemyProviderRegistryRepository,
    human_decision_id: UUID | None = None,
    learning_signal_id: UUID | None = None,
) -> ReferralData:
    provider = await registry.get_provider(item.provider_id)
    service = await registry.get_service(item.provider_service_id)
    if provider is None or service is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "REFERRAL_PROVIDER_REFERENCE_MISSING"},
        )
    return ReferralData(
        id=item.id,
        household_id=item.household_id,
        intervention_id=item.intervention_id,
        provider_match_id=item.provider_match_id,
        provider_selection_id=item.provider_selection_id,
        provider_id=item.provider_id,
        provider_name=provider.name,
        provider_service_id=item.provider_service_id,
        service_title=service.title,
        human_decision_id=human_decision_id,
        learning_signal_id=learning_signal_id,
        status=item.status,
        priority=item.priority,
        version=item.version,
        response_due_at=item.response_due_at,
        external_referral_id=item.external_referral_id,
        created_at=item.created_at,
        data_items=[
            ReferralDataItemData(
                id=data_item.id,
                data_category=data_item.data_category,
                source_fact_id=data_item.source_fact_id,
                snapshot_value=data_item.snapshot_value,
                purpose=data_item.purpose,
                authorization_basis=data_item.authorization_basis,
                shared_at=data_item.shared_at,
            )
            for data_item in item.data_items
        ],
    )


def _map_lifecycle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ReferralVersionConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT"},
        )
    if isinstance(exc, ReferralIdempotencyConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": str(exc)},
        )
    if isinstance(exc, ReferralProviderScopeError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": str(exc)},
    )


@router.post(
    "/api/v1/interventions/{intervention_id}/referrals",
    response_model=ReferralResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_referral(
    intervention_id: UUID,
    body: CreateReferralRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReferralResponse:
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
            registry = SqlAlchemyProviderRegistryRepository(session)
            referral, _selection, human, signal = await CreateReferralHandler(
                interventions=interventions,
                registry=registry,
                matches=SqlAlchemyProviderMatchRepository(session),
                selections=SqlAlchemyProviderSelectionRepository(session),
                referrals=SqlAlchemyReferralRepository(session),
                facts=SqlAlchemyHouseholdFactRepository(session),
                accepted_state=SqlAlchemyAcceptedStateRepository(session),
                human_decisions=SqlAlchemyHumanDecisionRepository(session),
                learning_signals=SqlAlchemyLearningSignalRepository(session),
                traces=SqlAlchemyDecisionTraceRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                CreateReferralCommand(
                    intervention_id=intervention_id,
                    provider_id=body.provider_id,
                    provider_service_id=body.provider_service_id,
                    priority=body.priority,
                    response_due_at=body.response_due_at,
                    shared_data_items=tuple(
                        SharedFactInput(
                            source_fact_id=item.source_fact_id,
                            purpose=item.purpose,
                        )
                        for item in body.shared_data_items
                    ),
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except ReferralCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return ReferralResponse(
        data=await _data(
            referral,
            registry=registry,
            human_decision_id=human.id,
            learning_signal_id=signal.id,
        )
    )


@router.post(
    "/api/v1/referrals/{referral_id}/send",
    response_model=SendReferralResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_referral(
    referral_id: UUID,
    body: SendReferralRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SendReferralResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    referrals = SqlAlchemyReferralRepository(session)

    try:
        async with session.begin():
            referral = await referrals.get(referral_id)
            if referral is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "RESOURCE_NOT_FOUND"},
                )
            await require_household_assignment(
                session=session,
                context=context,
                household_id=referral.household_id,
            )
            result = await SendReferralHandler(
                referrals=referrals,
                dispatches=SqlAlchemyReferralDispatchRepository(session),
                registry=SqlAlchemyProviderRegistryRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                SendReferralCommand(
                    referral_id=referral_id,
                    expected_version=body.expected_version,
                    idempotency_key=idempotency_key,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except (
        ReferralTransitionError,
        ReferralVersionConflictError,
        ReferralIdempotencyConflictError,
    ) as exc:
        raise _map_lifecycle_error(exc) from exc

    await start_referral_workflow_best_effort(
        referral=result.referral,
        dispatch=result.dispatch,
        actor_id=context.actor_id,
        settings=get_settings(),
    )

    return SendReferralResponse(
        data=SendReferralData(
            referral_id=result.referral.id,
            dispatch_id=result.dispatch.id,
            status=result.referral.status,
            version=result.referral.version,
            dispatch_status=result.dispatch.status,
            replayed=result.replayed,
        )
    )


@router.post(
    "/api/v1/referrals/{referral_id}/transition",
    response_model=ReferralResponse,
)
async def transition_referral(
    referral_id: UUID,
    body: TransitionReferralRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReferralResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    referrals = SqlAlchemyReferralRepository(session)

    try:
        async with session.begin():
            current = await referrals.get(referral_id)
            if current is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "RESOURCE_NOT_FOUND"},
                )
            await require_household_assignment(
                session=session,
                context=context,
                household_id=current.household_id,
            )
            updated = await TransitionReferralHandler(
                referrals=referrals,
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                TransitionReferralCommand(
                    referral_id=referral_id,
                    expected_version=body.expected_version,
                    to_status=body.to_status,
                    reason_code=body.reason_code,
                    occurred_at=body.occurred_at,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except (ReferralTransitionError, ReferralVersionConflictError) as exc:
        raise _map_lifecycle_error(exc) from exc

    if updated.status is ReferralStatus.CANCELLED:
        dispatch = await SqlAlchemyReferralDispatchRepository(
            session
        ).get_latest_for_referral(updated.id)
        if dispatch is not None:
            await signal_referral_cancelled_best_effort(
                referral_id=updated.id,
                dispatch_id=dispatch.id,
                settings=get_settings(),
            )

    return ReferralResponse(
        data=await _data(
            updated,
            registry=SqlAlchemyProviderRegistryRepository(session),
        )
    )


@router.get("/api/v1/referrals/{referral_id}", response_model=ReferralResponse)
async def get_referral(
    referral_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReferralResponse:
    item = await SqlAlchemyReferralRepository(session).get(referral_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=item.household_id,
    )
    return ReferralResponse(
        data=await _data(
            item,
            registry=SqlAlchemyProviderRegistryRepository(session),
        )
    )


@router.get(
    "/api/v1/interventions/{intervention_id}/referral",
    response_model=ReferralResponse,
)
async def get_latest_referral(
    intervention_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReferralResponse:
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
    item = await SqlAlchemyReferralRepository(
        session
    ).get_latest_for_intervention(intervention_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REFERRAL_NOT_FOUND"},
        )
    return ReferralResponse(
        data=await _data(
            item,
            registry=SqlAlchemyProviderRegistryRepository(session),
        )
    )


@router.get(
    "/api/v1/referrals/{referral_id}/events",
    response_model=ReferralTimelineResponse,
)
async def get_referral_events(
    referral_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReferralTimelineResponse:
    referrals = SqlAlchemyReferralRepository(session)
    item = await referrals.get(referral_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=item.household_id,
    )
    events = await referrals.list_events(referral_id)
    return ReferralTimelineResponse(
        data=[
            ReferralEventData(
                id=event.id,
                referral_version=event.referral_version,
                from_status=event.from_status,
                to_status=event.to_status,
                occurred_at=event.occurred_at,
                recorded_at=event.recorded_at,
                source=event.source.value,
                reason_code=event.reason_code,
                external_event_id=event.external_event_id,
            )
            for event in events
        ]
    )


@router.post(
    "/api/v1/provider-integrations/referrals/{external_referral_id}/status",
    response_model=ProviderCallbackResponse,
)
async def provider_status_callback(
    external_referral_id: str,
    body: ProviderStatusCallbackRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(get_provider_authorization_context),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderCallbackResponse:
    if context.provider_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN"},
        )
    correlation_id = current_correlation_id() or body.external_event_id

    try:
        async with session.begin():
            result = await ProviderStatusCallbackHandler(
                referrals=SqlAlchemyReferralRepository(session),
                inbox=SqlAlchemyProviderCallbackInboxRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                ProviderStatusCallbackCommand(
                    provider_id=context.provider_id,
                    actor_id=context.actor_id,
                    external_referral_id=external_referral_id,
                    external_event_id=body.external_event_id,
                    to_status=body.status,
                    occurred_at=body.occurred_at,
                    reason_code=body.reason_code,
                    schema_version=body.schema_version,
                    correlation_id=correlation_id,
                )
            )
    except (
        ReferralTransitionError,
        ReferralVersionConflictError,
        ReferralIdempotencyConflictError,
        ReferralProviderScopeError,
    ) as exc:
        raise _map_lifecycle_error(exc) from exc

    dispatch = await SqlAlchemyReferralDispatchRepository(
        session
    ).get_latest_for_referral(result.referral.id)
    if dispatch is not None:
        await signal_referral_provider_status_best_effort(
            referral_id=result.referral.id,
            dispatch_id=dispatch.id,
            status=body.status,
            settings=get_settings(),
        )

    return ProviderCallbackResponse(
        data=ProviderCallbackData(
            referral_id=result.referral.id,
            status=result.referral.status,
            version=result.referral.version,
            duplicate=result.duplicate,
        )
    )
