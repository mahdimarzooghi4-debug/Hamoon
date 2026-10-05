from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.household.api.schemas import (
    CreateHouseholdRequest,
    CreateHouseholdResponse,
    HouseholdData,
    HouseholdDetailResponse,
    HouseholdInterventionData,
    HouseholdListResponse,
    HouseholdPGORData,
    HouseholdSummaryData,
    HouseholdTimelineItemData,
    HouseholdTimelineResponse,
    HouseholdWorkItemData,
    ResponseMeta,
)
from hamoon.domains.household.application.commands import CreateHouseholdCommand
from hamoon.domains.household.application.handlers import CreateHouseholdHandler
from hamoon.domains.household.domain.entities import Household, HouseholdStatus
from hamoon.domains.household.domain.errors import HouseholdCaseCodeExistsError
from hamoon.domains.household.infrastructure.repositories import (
    SqlAlchemyCaseAssignmentRepository,
    SqlAlchemyHouseholdRepository,
)
from hamoon.domains.household.infrastructure.timeline import (
    SqlAlchemyHouseholdTimelineRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.domains.intervention.domain.entities import Intervention
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.operations.domain.entities import WorkItem
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyWorkItemRepository,
)
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORSnapshotRepository,
)
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(prefix="/api/v1/households", tags=["households"])


def _summary_data(
    household: Household,
    *,
    pgor: PGORSnapshot | None,
    intervention: Intervention | None,
    next_work_item: WorkItem | None,
) -> HouseholdSummaryData:
    return HouseholdSummaryData(
        id=household.id,
        case_code=household.case_code,
        lifecycle_status=household.lifecycle_status,
        organizational_unit_id=household.organizational_unit_id,
        primary_caseworker_id=household.primary_caseworker_id,
        version=household.version,
        pgor=(
            None
            if pgor is None
            else HouseholdPGORData(
                snapshot_id=pgor.id,
                assessment_id=pgor.assessment_id,
                calculated_at=pgor.calculated_at,
                p=pgor.p,
                g=pgor.g,
                o=pgor.o,
                r=pgor.r,
                e=pgor.e,
                e_band=pgor.e_band,
                bottleneck_variables=list(pgor.bottleneck_variables),
                data_quality_flags=list(pgor.data_quality_flags),
            )
        ),
        current_intervention=(
            None
            if intervention is None
            else HouseholdInterventionData(
                id=intervention.id,
                intervention_type=intervention.intervention_type,
                target_pgor_variable=intervention.target_pgor_variable,
                status=intervention.status,
            )
        ),
        next_work_item=(
            None
            if next_work_item is None
            else HouseholdWorkItemData(
                id=next_work_item.id,
                work_type=next_work_item.work_type,
                title=next_work_item.title,
                reason=next_work_item.reason,
                priority=next_work_item.priority,
                status=next_work_item.status,
                due_at=next_work_item.due_at,
                version=next_work_item.version,
            )
        ),
    )


async def _summary_maps(
    *,
    session: AsyncSession,
    actor_id: UUID,
    household_ids: list[UUID],
) -> tuple[
    dict[UUID, PGORSnapshot],
    dict[UUID, Intervention],
    dict[UUID, WorkItem],
]:
    pgor = await SqlAlchemyPGORSnapshotRepository(
        session
    ).list_latest_official_for_households(household_ids)
    interventions = await SqlAlchemyInterventionRepository(
        session
    ).list_current_for_households(household_ids)
    work_items = await SqlAlchemyWorkItemRepository(
        session
    ).list_next_for_households(
        actor_id=actor_id,
        household_ids=household_ids,
    )
    return pgor, interventions, work_items


@router.get("", response_model=HouseholdListResponse)
async def list_households(
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    query: Annotated[str | None, Query(alias="q", max_length=100)] = None,
    lifecycle_status: Annotated[HouseholdStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> HouseholdListResponse:
    households = await SqlAlchemyHouseholdRepository(session).list_for_actor(
        actor_id=context.actor_id,
        query=query,
        lifecycle_status=lifecycle_status,
        limit=limit,
    )
    household_ids = [item.id for item in households]
    pgor, interventions, work_items = await _summary_maps(
        session=session,
        actor_id=context.actor_id,
        household_ids=household_ids,
    )
    return HouseholdListResponse(
        data=[
            _summary_data(
                item,
                pgor=pgor.get(item.id),
                intervention=interventions.get(item.id),
                next_work_item=work_items.get(item.id),
            )
            for item in households
        ]
    )


@router.get("/{household_id}", response_model=HouseholdDetailResponse)
async def get_household(
    household_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HouseholdDetailResponse:
    household = await SqlAlchemyHouseholdRepository(session).get(household_id)
    if household is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=household_id,
    )
    pgor, interventions, work_items = await _summary_maps(
        session=session,
        actor_id=context.actor_id,
        household_ids=[household_id],
    )
    return HouseholdDetailResponse(
        data=_summary_data(
            household,
            pgor=pgor.get(household_id),
            intervention=interventions.get(household_id),
            next_work_item=work_items.get(household_id),
        )
    )


@router.get(
    "/{household_id}/timeline",
    response_model=HouseholdTimelineResponse,
)
async def get_household_timeline(
    household_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> HouseholdTimelineResponse:
    household = await SqlAlchemyHouseholdRepository(session).get(household_id)
    if household is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=household_id,
    )
    items = await SqlAlchemyHouseholdTimelineRepository(
        session
    ).list_for_household(
        household_id=household_id,
        limit=limit,
    )
    return HouseholdTimelineResponse(
        data=[
            HouseholdTimelineItemData(
                kind=item.kind,
                entity_id=item.entity_id,
                occurred_at=item.occurred_at,
                status=item.status,
                detail=item.detail,
            )
            for item in items
        ]
    )


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
