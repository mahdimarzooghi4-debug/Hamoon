from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.config.settings import get_settings
from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.assessment.infrastructure.repositories import (
    SqlAlchemyAssessmentRepository,
)
from hamoon.domains.intelligence.domain.decisions import HumanDecisionAction
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyAIDecisionRepository,
    SqlAlchemyDecisionTraceRepository,
    SqlAlchemyHumanDecisionRepository,
    SqlAlchemyLearningSignalRepository,
)
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.operations.application.handlers import FinalizeOutcomeReviewHandler
from hamoon.domains.operations.domain.entities import ReassessmentPlan
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyReassessmentPlanRepository,
    SqlAlchemyWorkItemRepository,
)
from hamoon.domains.outcome.api.schemas import (
    DeferOutcomeRequest,
    OutcomeData,
    OutcomeResponse,
    PrepareOutcomeRequest,
    ReviewOutcomeRequest,
)
from hamoon.domains.outcome.application.commands import (
    PrepareOutcomeCommand,
    ReviewOutcomeCommand,
)
from hamoon.domains.outcome.application.handlers import (
    PrepareOutcomeHandler,
    ReviewOutcomeHandler,
)
from hamoon.domains.outcome.domain.entities import (
    HamoonOutcome,
    OutcomeClassification,
    OutcomeStatus,
)
from hamoon.domains.outcome.domain.errors import (
    OutcomePreparationError,
    OutcomeReviewError,
    OutcomeVersionConflictError,
)
from hamoon.domains.outcome.infrastructure.repositories import (
    SqlAlchemyOutcomeInterpretationProposalRepository,
    SqlAlchemyOutcomeRepository,
)
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORSnapshotRepository,
)
from hamoon.domains.provider_result.infrastructure.repositories import (
    SqlAlchemyProviderResultRepository,
)
from hamoon.domains.referral.infrastructure.repositories import (
    SqlAlchemyReferralRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder
from hamoon.infrastructure.temporal.reassessment_starter import (
    signal_outcome_reviewed_best_effort,
)

router = APIRouter(tags=["outcome"])


def _data(
    item: HamoonOutcome,
    *,
    learning_signal_id: UUID | None = None,
) -> OutcomeData:
    return OutcomeData(
        id=item.id,
        household_id=item.household_id,
        intervention_id=item.intervention_id,
        referral_id=item.referral_id,
        provider_result_id=item.provider_result_id,
        pre_assessment_id=item.pre_assessment_id,
        post_assessment_id=item.post_assessment_id,
        pre_pgor_snapshot_id=item.pre_pgor_snapshot_id,
        post_pgor_snapshot_id=item.post_pgor_snapshot_id,
        status=item.status,
        classification=item.classification,
        observed_change_summary=item.observed_change_summary,
        p_delta=item.p_delta,
        g_delta=item.g_delta,
        o_delta=item.o_delta,
        r_delta=item.r_delta,
        e_delta=item.e_delta,
        confidence=item.confidence,
        methodology_version=item.methodology_version,
        version=item.version,
        assessed_at=item.assessed_at,
        latest_human_decision_id=item.latest_human_decision_id,
        learning_signal_id=learning_signal_id,
    )


@router.post(
    "/api/v1/interventions/{intervention_id}/outcomes/prepare",
    response_model=OutcomeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def prepare_outcome(
    intervention_id: UUID,
    body: PrepareOutcomeRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OutcomeResponse:
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
            outcome = await PrepareOutcomeHandler(
                interventions=interventions,
                assessments=SqlAlchemyAssessmentRepository(session),
                snapshots=SqlAlchemyPGORSnapshotRepository(session),
                provider_results=SqlAlchemyProviderResultRepository(session),
                referrals=SqlAlchemyReferralRepository(session),
                outcomes=SqlAlchemyOutcomeRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                PrepareOutcomeCommand(
                    intervention_id=intervention_id,
                    pre_assessment_id=body.pre_assessment_id,
                    post_assessment_id=body.post_assessment_id,
                    provider_result_id=body.provider_result_id,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except OutcomePreparationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc
    return OutcomeResponse(data=_data(outcome))


async def _review(
    *,
    outcome_id: UUID,
    expected_version: int,
    classification: OutcomeClassification,
    observed_change_summary: str | None,
    reason_code: str | None,
    reason_text: str | None,
    action: HumanDecisionAction,
    target_status: OutcomeStatus,
    context: AuthorizationContext,
    session: AsyncSession,
) -> OutcomeResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    repository = SqlAlchemyOutcomeRepository(session)
    completed_plan: ReassessmentPlan | None = None
    try:
        async with session.begin():
            current = await repository.get(outcome_id)
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
            updated, _human, signal = await ReviewOutcomeHandler(
                outcomes=repository,
                human_decisions=SqlAlchemyHumanDecisionRepository(session),
                learning_signals=SqlAlchemyLearningSignalRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
                proposals=SqlAlchemyOutcomeInterpretationProposalRepository(session),
                ai_decisions=SqlAlchemyAIDecisionRepository(session),
                traces=SqlAlchemyDecisionTraceRepository(session),
            ).handle(
                ReviewOutcomeCommand(
                    outcome_id=outcome_id,
                    expected_version=expected_version,
                    classification=classification,
                    observed_change_summary=observed_change_summary,
                    reason_code=reason_code,
                    reason_text=reason_text,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                ),
                action=action,
                target_status=target_status,
            )
            if target_status in {
                OutcomeStatus.CONFIRMED,
                OutcomeStatus.MODIFIED,
            }:
                completed_plan = await FinalizeOutcomeReviewHandler(
                    plans=SqlAlchemyReassessmentPlanRepository(session),
                    work_items=SqlAlchemyWorkItemRepository(session),
                    events=SqlAlchemyDomainEventRecorder(session),
                    audits=SqlAlchemyAuditRecorder(session),
                ).handle(
                    outcome_id=outcome_id,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
    except OutcomeVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT"},
        ) from exc
    except OutcomeReviewError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc
    except (LookupError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    if completed_plan is not None:
        await signal_outcome_reviewed_best_effort(
            plan=completed_plan,
            settings=get_settings(),
        )

    return OutcomeResponse(data=_data(updated, learning_signal_id=signal.id))


@router.post("/api/v1/outcomes/{outcome_id}/confirm", response_model=OutcomeResponse)
async def confirm_outcome(
    outcome_id: UUID,
    body: ReviewOutcomeRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OutcomeResponse:
    return await _review(
        outcome_id=outcome_id,
        expected_version=body.expected_version,
        classification=body.classification,
        observed_change_summary=body.observed_change_summary,
        reason_code=body.reason_code,
        reason_text=body.reason_text,
        action=HumanDecisionAction.CONFIRM,
        target_status=OutcomeStatus.CONFIRMED,
        context=context,
        session=session,
    )


@router.post("/api/v1/outcomes/{outcome_id}/modify", response_model=OutcomeResponse)
async def modify_outcome(
    outcome_id: UUID,
    body: ReviewOutcomeRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OutcomeResponse:
    return await _review(
        outcome_id=outcome_id,
        expected_version=body.expected_version,
        classification=body.classification,
        observed_change_summary=body.observed_change_summary,
        reason_code=body.reason_code,
        reason_text=body.reason_text,
        action=HumanDecisionAction.MODIFY,
        target_status=OutcomeStatus.MODIFIED,
        context=context,
        session=session,
    )


@router.post(
    "/api/v1/outcomes/{outcome_id}/needs-more-time",
    response_model=OutcomeResponse,
)
async def outcome_needs_more_time(
    outcome_id: UUID,
    body: DeferOutcomeRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OutcomeResponse:
    return await _review(
        outcome_id=outcome_id,
        expected_version=body.expected_version,
        classification=OutcomeClassification.NEEDS_MORE_TIME,
        observed_change_summary=None,
        reason_code=body.reason_code,
        reason_text=body.reason_text,
        action=HumanDecisionAction.DEFER,
        target_status=OutcomeStatus.NEEDS_MORE_TIME,
        context=context,
        session=session,
    )


@router.post(
    "/api/v1/outcomes/{outcome_id}/needs-more-data",
    response_model=OutcomeResponse,
)
async def outcome_needs_more_data(
    outcome_id: UUID,
    body: DeferOutcomeRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OutcomeResponse:
    return await _review(
        outcome_id=outcome_id,
        expected_version=body.expected_version,
        classification=OutcomeClassification.NEEDS_MORE_DATA,
        observed_change_summary=None,
        reason_code=body.reason_code,
        reason_text=body.reason_text,
        action=HumanDecisionAction.DEFER,
        target_status=OutcomeStatus.NEEDS_MORE_DATA,
        context=context,
        session=session,
    )


@router.get("/api/v1/outcomes/{outcome_id}", response_model=OutcomeResponse)
async def get_outcome(
    outcome_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OutcomeResponse:
    item = await SqlAlchemyOutcomeRepository(session).get(outcome_id)
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
    return OutcomeResponse(data=_data(item))
