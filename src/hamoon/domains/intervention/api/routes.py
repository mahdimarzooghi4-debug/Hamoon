from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyDecisionTraceRepository,
)
from hamoon.domains.intervention.api.schemas import (
    InterventionData,
    InterventionListResponse,
    InterventionResponse,
)
from hamoon.domains.intervention.application.commands import ActivateInterventionCommand
from hamoon.domains.intervention.application.handlers import ActivateInterventionHandler
from hamoon.domains.intervention.domain.entities import Intervention
from hamoon.domains.intervention.domain.errors import InterventionActivationError
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.prescription.infrastructure.repositories import (
    SqlAlchemyPrescriptionRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["intervention"])


def _data(item: Intervention) -> InterventionData:
    return InterventionData(
        id=item.id,
        household_id=item.household_id,
        prescription_item_id=item.prescription_item_id,
        intervention_type=item.intervention_type,
        target_pgor_variable=item.target_pgor_variable,
        status=item.status,
        started_at=item.started_at,
        completed_at=item.completed_at,
        owner_actor_id=item.owner_actor_id,
    )


@router.post(
    "/api/v1/prescriptions/{prescription_id}/items/{item_id}/activate",
    response_model=InterventionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def activate_intervention(
    prescription_id: UUID,
    item_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterventionResponse:
    prescriptions = SqlAlchemyPrescriptionRepository(session)
    prescription = await prescriptions.get(prescription_id)
    if prescription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=prescription.household_id,
    )

    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    try:
        async with session.begin():
            intervention = await ActivateInterventionHandler(
                prescriptions=prescriptions,
                interventions=SqlAlchemyInterventionRepository(session),
                traces=SqlAlchemyDecisionTraceRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                ActivateInterventionCommand(
                    prescription_id=prescription_id,
                    prescription_item_id=item_id,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except InterventionActivationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return InterventionResponse(data=_data(intervention))


@router.get(
    "/api/v1/households/{household_id}/interventions",
    response_model=InterventionListResponse,
)
async def list_interventions(
    household_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterventionListResponse:
    await require_household_assignment(
        session=session,
        context=context,
        household_id=household_id,
    )
    items = await SqlAlchemyInterventionRepository(session).list_for_household(
        household_id
    )
    return InterventionListResponse(data=[_data(item) for item in items])


@router.get(
    "/api/v1/interventions/{intervention_id}",
    response_model=InterventionResponse,
)
async def get_intervention(
    intervention_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterventionResponse:
    item = await SqlAlchemyInterventionRepository(session).get(intervention_id)
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
    return InterventionResponse(data=_data(item))
