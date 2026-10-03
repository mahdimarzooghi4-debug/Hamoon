from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.operations.api.schemas import (
    ClaimWorkItemRequest,
    StartWorkItemReassessmentData,
    StartWorkItemReassessmentRequest,
    StartWorkItemReassessmentResponse,
    HouseholdTimelineResponse,
    TimelineItemData,
    WorkItemData,
    WorkItemResponse,
    WorkQueueResponse,
)
from hamoon.domains.operations.application.handlers import (
    StartPlannedReassessmentHandler,
)
from hamoon.domains.operations.domain.entities import WorkItem, WorkItemStatus
from hamoon.domains.assessment.infrastructure.repositories import (
    SqlAlchemyAssessmentRepository,
)
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyReassessmentPlanRepository,
    SqlAlchemyWorkItemRepository,
)
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORDefinitionRepository,
    SqlAlchemyPGORSnapshotRepository,
)
from hamoon.domains.prescription.infrastructure.repositories import (
    SqlAlchemyPrescriptionRepository,
)
from hamoon.domains.provider_result.infrastructure.repositories import (
    SqlAlchemyProviderResultRepository,
)
from hamoon.domains.referral.infrastructure.repositories import (
    SqlAlchemyReferralRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.models import DomainEventModel


router = APIRouter(tags=["operations"])


def _work_item_data(item: WorkItem) -> WorkItemData:
    return WorkItemData(
        id=item.id,
        household_id=item.household_id,
        work_type=item.work_type,
        resource_type=item.resource_type,
        resource_id=item.resource_id,
        title=item.title,
        reason=item.reason,
        priority=item.priority,
        status=item.status,
        version=item.version,
        due_at=item.due_at,
        assigned_actor_id=item.assigned_actor_id,
        policy_version=item.policy_version,
        created_at=item.created_at,
        claimed_at=item.claimed_at,
    )


@router.get("/api/v1/work-queue", response_model=WorkQueueResponse)
async def get_work_queue(
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    due_before: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> WorkQueueResponse:
    items = await SqlAlchemyWorkItemRepository(session).list_for_actor(
        actor_id=context.actor_id,
        statuses=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        due_before=due_before,
        limit=limit,
    )
    return WorkQueueResponse(data=[_work_item_data(item) for item in items])


@router.post(
    "/api/v1/work-queue/{work_item_id}/claim",
    response_model=WorkItemResponse,
)
async def claim_work_item(
    work_item_id: UUID,
    body: ClaimWorkItemRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkItemResponse:
    repository = SqlAlchemyWorkItemRepository(session)
    try:
        async with session.begin():
            item = await repository.get(work_item_id)
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
            if item.version != body.expected_version:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "VERSION_CONFLICT"},
                )
            updated = item.claim(actor_id=context.actor_id, claimed_at=datetime.now(UTC))
            await repository.update(updated, expected_version=item.version)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc
    return WorkItemResponse(data=_work_item_data(updated))


@router.post(
    "/api/v1/work-queue/{work_item_id}/reassessment/start",
    response_model=StartWorkItemReassessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_work_item_reassessment(
    work_item_id: UUID,
    body: StartWorkItemReassessmentRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StartWorkItemReassessmentResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    repository = SqlAlchemyWorkItemRepository(session)
    try:
        async with session.begin():
            item = await repository.get(work_item_id)
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
            assessment, updated_item, plan = await StartPlannedReassessmentHandler(
                plans=SqlAlchemyReassessmentPlanRepository(session),
                work_items=repository,
                assessments=SqlAlchemyAssessmentRepository(session),
                definitions=SqlAlchemyPGORDefinitionRepository(session),
                interventions=SqlAlchemyInterventionRepository(session),
                provider_results=SqlAlchemyProviderResultRepository(session),
                referrals=SqlAlchemyReferralRepository(session),
                prescriptions=SqlAlchemyPrescriptionRepository(session),
                snapshots=SqlAlchemyPGORSnapshotRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                work_item_id=work_item_id,
                expected_version=body.expected_version,
                actor_id=context.actor_id,
                request_id=request_id,
                correlation_id=correlation_id,
            )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": str(exc)},
        ) from exc
    except ValueError as exc:
        code = str(exc)
        http_status = (
            status.HTTP_409_CONFLICT
            if code == "WORK_ITEM_VERSION_CONFLICT"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(
            status_code=http_status,
            detail={"code": code},
        ) from exc

    return StartWorkItemReassessmentResponse(
        data=StartWorkItemReassessmentData(
            work_item=_work_item_data(updated_item),
            assessment_id=assessment.id,
            reassessment_plan_id=plan.id,
            definition_version_id=assessment.definition_version_id,
            parent_assessment_id=assessment.parent_assessment_id,
        )
    )


@router.get(
    "/api/v1/households/{household_id}/timeline",
    response_model=HouseholdTimelineResponse,
)
async def get_household_timeline(
    household_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> HouseholdTimelineResponse:
    await require_household_assignment(
        session=session,
        context=context,
        household_id=household_id,
    )
    result = await session.execute(
        select(DomainEventModel)
        .where(
            or_(
                (
                    (DomainEventModel.aggregate_type == "HOUSEHOLD")
                    & (DomainEventModel.aggregate_id == household_id)
                ),
                DomainEventModel.payload["household_id"].as_string()
                == str(household_id),
            )
        )
        .order_by(DomainEventModel.occurred_at.desc())
        .limit(limit)
    )
    return HouseholdTimelineResponse(
        data=[
            TimelineItemData(
                event_id=item.event_id,
                event_type=item.event_type,
                aggregate_type=item.aggregate_type,
                aggregate_id=item.aggregate_id,
                occurred_at=item.occurred_at,
                actor_id=item.actor_id,
                correlation_id=item.correlation_id,
            )
            for item in result.scalars().all()
        ]
    )
