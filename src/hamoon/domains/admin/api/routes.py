from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.domains.admin.api.schemas import (
    DataHealthData,
    DataHealthResponse,
    MachineHealthData,
    MachineHealthResponse,
)
from hamoon.domains.assessment.domain.entities import AssessmentStatus
from hamoon.domains.assessment.infrastructure.models import AssessmentModel
from hamoon.domains.evidence.domain.entities import EvidenceLifecycleStatus
from hamoon.domains.evidence.infrastructure.models import EvidenceModel
from hamoon.domains.family_data.domain.entities import FactValidationStatus
from hamoon.domains.family_data.infrastructure.models import FactValidationStateModel
from hamoon.domains.intelligence.domain.decisions import (
    HumanDecisionAction,
    LearningSignalQuality,
)
from hamoon.domains.intelligence.domain.registry import (
    EvaluationStatus,
    RoutingPolicyStatus,
)
from hamoon.domains.intelligence.infrastructure.models import (
    AIDecisionModel,
    EvaluationRunModel,
    HumanDecisionModel,
    LearningSignalModel,
    ModelRoutingPolicyModel,
)
from hamoon.domains.operations.domain.entities import (
    ReassessmentPlanStatus,
    WorkItemStatus,
)
from hamoon.domains.operations.infrastructure.models import (
    ReassessmentPlanModel,
    WorkItemModel,
)
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.models import OutboxMessageModel

router = APIRouter(tags=["admin-health"])


async def _scalar_count(
    session: AsyncSession,
    statement: Select[tuple[int]],
) -> int:
    value = await session.scalar(statement)
    return int(value or 0)


@router.get(
    "/api/v1/admin/health/data",
    response_model=DataHealthResponse,
)
async def get_data_health(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN, Role.SECURITY_AUDITOR)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataHealthResponse:
    now = datetime.now(UTC)
    pending_validation = await _scalar_count(
        session,
        select(func.count())
        .select_from(FactValidationStateModel)
        .where(
            FactValidationStateModel.status
            == FactValidationStatus.PENDING_VALIDATION
        ),
    )
    disputed = await _scalar_count(
        session,
        select(func.count())
        .select_from(FactValidationStateModel)
        .where(FactValidationStateModel.status == FactValidationStatus.DISPUTED),
    )
    incomplete_assessments = await _scalar_count(
        session,
        select(func.count())
        .select_from(AssessmentModel)
        .where(AssessmentModel.status != AssessmentStatus.COMPLETED),
    )
    overdue_work_items = await _scalar_count(
        session,
        select(func.count())
        .select_from(WorkItemModel)
        .where(
            WorkItemModel.status.in_(
                (WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
            ),
            WorkItemModel.due_at.is_not(None),
            WorkItemModel.due_at < now,
        ),
    )
    pending_outbox = await _scalar_count(
        session,
        select(func.count())
        .select_from(OutboxMessageModel)
        .where(OutboxMessageModel.published_at.is_(None)),
    )
    quarantined_evidence = await _scalar_count(
        session,
        select(func.count())
        .select_from(EvidenceModel)
        .where(
            EvidenceModel.lifecycle_status
            == EvidenceLifecycleStatus.QUARANTINED
        ),
    )
    return DataHealthResponse(
        data=DataHealthData(
            pending_validation_facts=pending_validation,
            disputed_facts=disputed,
            incomplete_assessments=incomplete_assessments,
            overdue_work_items=overdue_work_items,
            pending_outbox_messages=pending_outbox,
            quarantined_evidence=quarantined_evidence,
            generated_at=now,
        )
    )


@router.get(
    "/api/v1/admin/health/machine",
    response_model=MachineHealthResponse,
)
async def get_machine_health(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN, Role.SECURITY_AUDITOR)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MachineHealthResponse:
    now = datetime.now(UTC)

    async def decision_count(action: HumanDecisionAction) -> int:
        return await _scalar_count(
            session,
            select(func.count())
            .select_from(HumanDecisionModel)
            .where(HumanDecisionModel.action == action),
        )

    async def signal_count(quality: LearningSignalQuality) -> int:
        return await _scalar_count(
            session,
            select(func.count())
            .select_from(LearningSignalModel)
            .where(LearningSignalModel.quality_status == quality),
        )

    async def evaluation_count(status: EvaluationStatus) -> int:
        return await _scalar_count(
            session,
            select(func.count())
            .select_from(EvaluationRunModel)
            .where(EvaluationRunModel.status == status),
        )

    ai_decisions_total = await _scalar_count(
        session,
        select(func.count()).select_from(AIDecisionModel),
    )
    active_routing = await _scalar_count(
        session,
        select(func.count())
        .select_from(ModelRoutingPolicyModel)
        .where(ModelRoutingPolicyModel.status == RoutingPolicyStatus.ACTIVE),
    )
    incomplete_reassessments = await _scalar_count(
        session,
        select(func.count())
        .select_from(ReassessmentPlanModel)
        .where(
            ReassessmentPlanModel.status.not_in(
                (
                    ReassessmentPlanStatus.COMPLETED,
                    ReassessmentPlanStatus.CANCELLED,
                )
            )
        ),
    )

    return MachineHealthResponse(
        data=MachineHealthData(
            ai_decisions_total=ai_decisions_total,
            human_confirm_total=await decision_count(HumanDecisionAction.CONFIRM),
            human_modify_total=await decision_count(HumanDecisionAction.MODIFY),
            human_replace_total=await decision_count(HumanDecisionAction.REPLACE),
            human_reject_total=await decision_count(HumanDecisionAction.REJECT),
            human_defer_total=await decision_count(HumanDecisionAction.DEFER),
            learning_signal_raw=await signal_count(LearningSignalQuality.RAW),
            learning_signal_curated=await signal_count(
                LearningSignalQuality.CURATED
            ),
            learning_signal_excluded=await signal_count(
                LearningSignalQuality.EXCLUDED
            ),
            evaluation_pending=(
                await evaluation_count(EvaluationStatus.PENDING)
                + await evaluation_count(EvaluationStatus.RUNNING)
            ),
            evaluation_passed=await evaluation_count(EvaluationStatus.PASSED),
            evaluation_failed=await evaluation_count(EvaluationStatus.FAILED),
            active_routing_policies=active_routing,
            incomplete_reassessment_plans=incomplete_reassessments,
            generated_at=now,
        )
    )
