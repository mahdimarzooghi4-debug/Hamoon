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
    SqlAlchemyHouseholdFactRepository,
)
from hamoon.domains.intelligence.infrastructure.repositories import (
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
    ReferralData,
    ReferralDataItemData,
    ReferralResponse,
)
from hamoon.domains.referral.application.commands import (
    CreateReferralCommand,
    SharedFactInput,
)
from hamoon.domains.referral.application.handlers import CreateReferralHandler
from hamoon.domains.referral.domain.entities import Referral
from hamoon.domains.referral.domain.errors import ReferralCreationError
from hamoon.domains.referral.infrastructure.repositories import (
    SqlAlchemyReferralRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["referral"])


def _data(
    item: Referral,
    *,
    human_decision_id: UUID | None = None,
    learning_signal_id: UUID | None = None,
) -> ReferralData:
    return ReferralData(
        id=item.id,
        household_id=item.household_id,
        intervention_id=item.intervention_id,
        provider_match_id=item.provider_match_id,
        provider_selection_id=item.provider_selection_id,
        provider_id=item.provider_id,
        provider_service_id=item.provider_service_id,
        human_decision_id=human_decision_id,
        learning_signal_id=learning_signal_id,
        status=item.status,
        priority=item.priority,
        version=item.version,
        response_due_at=item.response_due_at,
        created_at=item.created_at,
        data_items=[
            ReferralDataItemData(
                id=data_item.id,
                data_category=data_item.data_category,
                source_fact_id=data_item.source_fact_id,
                snapshot_value=data_item.snapshot_value,
                purpose=data_item.purpose,
                shared_at=data_item.shared_at,
            )
            for data_item in item.data_items
        ],
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
            referral, _selection, human, signal = await CreateReferralHandler(
                interventions=interventions,
                registry=SqlAlchemyProviderRegistryRepository(session),
                matches=SqlAlchemyProviderMatchRepository(session),
                selections=SqlAlchemyProviderSelectionRepository(session),
                referrals=SqlAlchemyReferralRepository(session),
                facts=SqlAlchemyHouseholdFactRepository(session),
                accepted_state=SqlAlchemyAcceptedStateRepository(session),
                human_decisions=SqlAlchemyHumanDecisionRepository(session),
                learning_signals=SqlAlchemyLearningSignalRepository(session),
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
        data=_data(
            referral,
            human_decision_id=human.id,
            learning_signal_id=signal.id,
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
    return ReferralResponse(data=_data(item))
