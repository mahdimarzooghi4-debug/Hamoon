from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.domains.household.api.schemas import (
    CreateHouseholdRequest,
    CreateHouseholdResponse,
    HouseholdData,
    ResponseMeta,
)
from hamoon.domains.household.application.commands import CreateHouseholdCommand
from hamoon.domains.household.application.handlers import CreateHouseholdHandler
from hamoon.domains.household.domain.errors import HouseholdCaseCodeExistsError
from hamoon.domains.household.infrastructure.repositories import (
    SqlAlchemyCaseAssignmentRepository,
    SqlAlchemyHouseholdRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(prefix="/api/v1/households", tags=["households"])


@router.post("", response_model=CreateHouseholdResponse, status_code=status.HTTP_201_CREATED)
async def create_household(
    body: CreateHouseholdRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CreateHouseholdResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id

    if (
        body.organizational_unit_id is not None
        and context.unit_id is not None
        and body.organizational_unit_id != context.unit_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "UNIT_SCOPE_VIOLATION"},
        )

    organizational_unit_id = body.organizational_unit_id or context.unit_id

    handler = CreateHouseholdHandler(
        households=SqlAlchemyHouseholdRepository(session),
        assignments=SqlAlchemyCaseAssignmentRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )

    try:
        async with session.begin():
            household = await handler.handle(
                CreateHouseholdCommand(
                    case_code=body.case_code,
                    actor_id=context.actor_id,
                    organizational_unit_id=organizational_unit_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except HouseholdCaseCodeExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "HOUSEHOLD_CASE_CODE_EXISTS"},
        ) from exc

    return CreateHouseholdResponse(
        data=HouseholdData(
            id=household.id,
            case_code=household.case_code,
            lifecycle_status=household.lifecycle_status,
            organizational_unit_id=household.organizational_unit_id,
            primary_caseworker_id=household.primary_caseworker_id,
            version=household.version,
        ),
        meta=ResponseMeta(
            request_id=request_id,
            version=household.version,
        ),
    )
