from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.config.settings import get_settings
from hamoon.app.observability.request_context import current_correlation_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import (
    get_provider_authorization_context,
    require_roles,
)
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyReassessmentPlanRepository,
)
from hamoon.domains.prescription.infrastructure.repositories import (
    SqlAlchemyPrescriptionRepository,
)
from hamoon.domains.provider_result.api.schemas import (
    ProviderResultData,
    ProviderResultListResponse,
    ProviderResultResponse,
    SubmitProviderResultRequest,
)
from hamoon.domains.provider_result.application.commands import (
    SubmitProviderResultCommand,
)
from hamoon.domains.provider_result.application.handlers import (
    SubmitProviderResultHandler,
)
from hamoon.domains.provider_result.domain.entities import ProviderResult
from hamoon.domains.provider_result.domain.errors import (
    ProviderResultError,
    ProviderResultIdempotencyConflictError,
    ProviderResultScopeError,
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
    start_reassessment_best_effort,
)

router = APIRouter(tags=["provider-result"])


def _data(
    item: ProviderResult,
    *,
    duplicate: bool = False,
    reassessment_plan_id: UUID | None = None,
    reassessment_due_at: datetime | None = None,
    workflow_id: str | None = None,
) -> ProviderResultData:
    return ProviderResultData(
        id=item.id,
        referral_id=item.referral_id,
        provider_id=item.provider_id,
        result_status=item.result_status,
        result_type=item.result_type,
        result_summary=item.result_summary,
        result_payload=item.result_payload,
        service_started_at=item.service_started_at,
        service_completed_at=item.service_completed_at,
        submitted_at=item.submitted_at,
        external_result_id=item.external_result_id,
        provider_reference=item.provider_reference,
        evidence=list(item.evidence_ids),
        duplicate=duplicate,
        reassessment_plan_id=reassessment_plan_id,
        reassessment_due_at=reassessment_due_at,
        workflow_id=workflow_id,
    )


@router.post(
    "/api/v1/provider-integrations/referrals/{external_referral_id}/results",
    response_model=ProviderResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_provider_result(
    external_referral_id: str,
    body: SubmitProviderResultRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(get_provider_authorization_context),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderResultResponse:
    if context.provider_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN"},
        )
    correlation_id = current_correlation_id() or body.external_result_id

    try:
        async with session.begin():
            result = await SubmitProviderResultHandler(
                referrals=SqlAlchemyReferralRepository(session),
                results=SqlAlchemyProviderResultRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
                interventions=SqlAlchemyInterventionRepository(session),
                prescriptions=SqlAlchemyPrescriptionRepository(session),
                reassessment_plans=SqlAlchemyReassessmentPlanRepository(session),
            ).handle(
                SubmitProviderResultCommand(
                    provider_id=context.provider_id,
                    actor_id=context.actor_id,
                    external_referral_id=external_referral_id,
                    external_result_id=body.external_result_id,
                    result_status=body.result_status,
                    result_type=body.result_type,
                    result_summary=body.result_summary,
                    result_payload=body.result_payload,
                    service_started_at=body.service_started_at,
                    service_completed_at=body.service_completed_at,
                    evidence_ids=tuple(body.evidence),
                    provider_reference=body.provider_reference,
                    correlation_id=correlation_id,
                )
            )
    except ProviderResultIdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": str(exc)},
        ) from exc
    except ProviderResultScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        ) from exc
    except ProviderResultError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    plan = result.reassessment_plan
    if plan is not None:
        await start_reassessment_best_effort(
            plan=plan,
            settings=get_settings(),
        )

    return ProviderResultResponse(
        data=_data(
            result.result,
            duplicate=result.duplicate,
            reassessment_plan_id=None if plan is None else plan.id,
            reassessment_due_at=None if plan is None else plan.due_at,
            workflow_id=None if plan is None else plan.workflow_id,
        )
    )


@router.get(
    "/api/v1/referrals/{referral_id}/provider-results",
    response_model=ProviderResultListResponse,
)
async def list_provider_results(
    referral_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderResultListResponse:
    referral = await SqlAlchemyReferralRepository(session).get(referral_id)
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
    results = await SqlAlchemyProviderResultRepository(session).list_for_referral(
        referral_id
    )
    return ProviderResultListResponse(data=[_data(item) for item in results])


@router.get(
    "/api/v1/provider-results/{result_id}",
    response_model=ProviderResultResponse,
)
async def get_provider_result(
    result_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProviderResultResponse:
    item = await SqlAlchemyProviderResultRepository(session).get(result_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    referral = await SqlAlchemyReferralRepository(session).get(item.referral_id)
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
    return ProviderResultResponse(data=_data(item))
