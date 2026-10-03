from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.family_data.api.schemas import (
    AcceptedFactData,
    AcceptedFactResponse,
    AcceptedStateResponse,
    ChangeValidationRequest,
    DataSourceData,
    DataSourceListResponse,
    FactData,
    FactListResponse,
    FactResponse,
    RecordFactRequest,
    ResolveAcceptedFactRequest,
    ValidationData,
    ValidationResponse,
)
from hamoon.domains.family_data.application.commands import (
    ChangeFactValidationCommand,
    RecordHouseholdFactCommand,
    ResolveAcceptedFactCommand,
)
from hamoon.domains.family_data.application.handlers import (
    ChangeFactValidationHandler,
    RecordHouseholdFactHandler,
    ResolveAcceptedFactHandler,
)
from hamoon.domains.family_data.domain.errors import (
    DataSourceNotFoundError,
    FactNotValidatedError,
    FactTypeMismatchError,
    HouseholdFactNotFoundError,
    InvalidFactValueError,
    InvalidValidationTransitionError,
    ProjectionVersionConflictError,
)
from hamoon.domains.family_data.infrastructure.repositories import (
    SqlAlchemyAcceptedStateRepository,
    SqlAlchemyDataSourceRepository,
    SqlAlchemyFactValidationRepository,
    SqlAlchemyHouseholdFactRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["family-data"])


def _fact_data(fact: object, validation: object) -> FactData:
    from hamoon.domains.family_data.domain.entities import FactValidationState, HouseholdFact

    typed_fact = cast(HouseholdFact, fact)
    typed_validation = cast(FactValidationState, validation)
    return FactData(
        id=typed_fact.id,
        household_id=typed_fact.household_id,
        fact_type=typed_fact.fact_type,
        value_type=typed_fact.value_type,
        value=cast(JsonValue, typed_fact.value),
        source_id=typed_fact.source_id,
        source_detail=typed_fact.source_detail,
        effective_from=typed_fact.effective_from,
        recorded_at=typed_fact.recorded_at,
        version=typed_fact.version,
        validation_status=typed_validation.status,
        validation_version=typed_validation.version,
    )


@router.get("/api/v1/data-sources", response_model=DataSourceListResponse)
async def list_data_sources(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataSourceListResponse:
    sources = await SqlAlchemyDataSourceRepository(session).list_active()
    return DataSourceListResponse(
        data=[
            DataSourceData(
                id=source.id,
                code=source.code,
                source_type=source.source_type,
                name=source.name,
            )
            for source in sources
        ]
    )


@router.post(
    "/api/v1/households/{household_id}/facts",
    response_model=FactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_fact(
    household_id: UUID,
    body: RecordFactRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FactResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id

    facts = SqlAlchemyHouseholdFactRepository(session)
    validations = SqlAlchemyFactValidationRepository(session)
    handler = RecordHouseholdFactHandler(
        sources=SqlAlchemyDataSourceRepository(session),
        facts=facts,
        validations=validations,
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )

    try:
        async with session.begin():
            await require_household_assignment(
                session=session,
                context=context,
                household_id=household_id,
            )
            fact = await handler.handle(
                RecordHouseholdFactCommand(
                    household_id=household_id,
                    actor_id=context.actor_id,
                    fact_type=body.fact_type,
                    value_type=body.value_type,
                    value=body.value,
                    source_id=body.source_id,
                    source_detail=body.source_detail,
                    effective_from=body.effective_from,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
            validation = await validations.get_state(fact.id)
            assert validation is not None
    except DataSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "DATA_SOURCE_NOT_FOUND"},
        ) from exc
    except InvalidFactValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_FACT_VALUE"},
        ) from exc

    return FactResponse(data=_fact_data(fact, validation))


@router.get(
    "/api/v1/households/{household_id}/facts",
    response_model=FactListResponse,
)
async def list_facts(
    household_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FactListResponse:
    await require_household_assignment(
        session=session,
        context=context,
        household_id=household_id,
    )
    facts_repo = SqlAlchemyHouseholdFactRepository(session)
    validation_repo = SqlAlchemyFactValidationRepository(session)
    facts = await facts_repo.list_for_household(household_id)

    data: list[FactData] = []
    for fact in facts:
        validation = await validation_repo.get_state(fact.id)
        if validation is not None:
            data.append(_fact_data(fact, validation))
    return FactListResponse(data=data)


@router.post(
    "/api/v1/households/{household_id}/facts/{fact_id}/validation",
    response_model=ValidationResponse,
)
async def change_fact_validation(
    household_id: UUID,
    fact_id: UUID,
    body: ChangeValidationRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ValidationResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    handler = ChangeFactValidationHandler(
        facts=SqlAlchemyHouseholdFactRepository(session),
        validations=SqlAlchemyFactValidationRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )

    try:
        async with session.begin():
            await require_household_assignment(
                session=session,
                context=context,
                household_id=household_id,
            )
            result = await handler.handle(
                ChangeFactValidationCommand(
                    household_id=household_id,
                    fact_id=fact_id,
                    actor_id=context.actor_id,
                    to_status=body.to_status,
                    expected_validation_version=body.expected_validation_version,
                    reason_code=body.reason_code,
                    reason_text=body.reason_text,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except HouseholdFactNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        ) from exc
    except InvalidValidationTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_FACT_VALIDATION_TRANSITION"},
        ) from exc
    except ProjectionVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT"},
        ) from exc

    return ValidationResponse(
        data=ValidationData(
            fact_id=result.fact_id,
            status=result.status,
            version=result.version,
            changed_at=result.changed_at,
            reason_code=result.reason_code,
            reason_text=result.reason_text,
        )
    )


@router.get(
    "/api/v1/households/{household_id}/accepted-state",
    response_model=AcceptedStateResponse,
)
async def get_accepted_state(
    household_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AcceptedStateResponse:
    await require_household_assignment(
        session=session,
        context=context,
        household_id=household_id,
    )
    items = await SqlAlchemyAcceptedStateRepository(session).list_for_household(
        household_id
    )
    return AcceptedStateResponse(
        data=[
            AcceptedFactData(
                household_id=item.household_id,
                fact_type=item.fact_type,
                fact_id=item.fact_id,
                accepted_value=cast(JsonValue, item.accepted_value),
                source_id=item.source_id,
                effective_from=item.effective_from,
                projection_version=item.projection_version,
                projected_at=item.projected_at,
            )
            for item in items
        ]
    )


@router.post(
    "/api/v1/households/{household_id}/accepted-state/{fact_type}/resolve",
    response_model=AcceptedFactResponse,
)
async def resolve_accepted_state(
    household_id: UUID,
    fact_type: str,
    body: ResolveAcceptedFactRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AcceptedFactResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    normalized_fact_type = fact_type.upper()

    handler = ResolveAcceptedFactHandler(
        facts=SqlAlchemyHouseholdFactRepository(session),
        validations=SqlAlchemyFactValidationRepository(session),
        accepted_state=SqlAlchemyAcceptedStateRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )

    try:
        async with session.begin():
            await require_household_assignment(
                session=session,
                context=context,
                household_id=household_id,
            )
            result = await handler.handle(
                ResolveAcceptedFactCommand(
                    household_id=household_id,
                    fact_type=normalized_fact_type,
                    fact_id=body.fact_id,
                    actor_id=context.actor_id,
                    expected_projection_version=body.expected_projection_version,
                    reason_code=body.reason_code,
                    reason_text=body.reason_text,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except HouseholdFactNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        ) from exc
    except FactTypeMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "FACT_TYPE_MISMATCH"},
        ) from exc
    except FactNotValidatedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "FACT_NOT_VALIDATED"},
        ) from exc
    except ProjectionVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT"},
        ) from exc

    return AcceptedFactResponse(
        data=AcceptedFactData(
            household_id=result.household_id,
            fact_type=result.fact_type,
            fact_id=result.fact_id,
            accepted_value=cast(JsonValue, result.accepted_value),
            source_id=result.source_id,
            effective_from=result.effective_from,
            projection_version=result.projection_version,
            projected_at=result.projected_at,
        )
    )
