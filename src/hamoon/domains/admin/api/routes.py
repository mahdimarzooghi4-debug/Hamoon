from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from hamoon.app.observability.metrics import SECURITY_DENIALS
from hamoon.app.observability.operational_events import (
    OperationalRuntimeEventModel,
    OperationalRuntimeEventType,
)
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.domains.admin.api.schemas import (
    DataHealthData,
    DataHealthResponse,
    EmpowermentOverviewData,
    EmpowermentOverviewResponse,
    PGORDistributionData,
    MachineHealthData,
    MachineHealthResponse,
)
from hamoon.domains.admin.infrastructure.empowerment import (
    SqlAlchemyEmpowermentOverviewRepository,
    VariableDistribution,
)
from hamoon.domains.assessment.domain.entities import AssessmentStatus
from hamoon.domains.assessment.infrastructure.models import AssessmentModel
from hamoon.domains.evidence.domain.entities import EvidenceLifecycleStatus
from hamoon.domains.evidence.infrastructure.models import EvidenceModel
from hamoon.domains.family_data.domain.entities import FactValidationStatus
from hamoon.domains.family_data.infrastructure.models import (
    CurrentAcceptedFactModel,
    FactValidationStateModel,
    HouseholdFactModel,
)
from hamoon.domains.intelligence.domain.decisions import (
    HumanDecisionAction,
    HumanDecisionContext,
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
    WorkItemType,
)
from hamoon.domains.operations.infrastructure.models import (
    ReassessmentPlanModel,
    WorkItemModel,
)
from hamoon.domains.referral.domain.entities import IntegrationProcessingStatus
from hamoon.domains.referral.infrastructure.models import (
    IntegrationMessageModel,
    ReferralDispatchModel,
)
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.models import OutboxMessageModel

router = APIRouter(tags=["admin-health"])


async def _scalar_count(
    session: AsyncSession,
    statement: Select[int],
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
    missing_required_data = await _scalar_count(
        session,
        select(func.count())
        .select_from(WorkItemModel)
        .where(
            WorkItemModel.work_type == WorkItemType.DATA_COMPLETION,
            WorkItemModel.status.in_(
                (WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
            ),
        ),
    )
    stale_source_data = await _scalar_count(
        session,
        select(func.count())
        .select_from(CurrentAcceptedFactModel)
        .join(
            HouseholdFactModel,
            HouseholdFactModel.id == CurrentAcceptedFactModel.fact_id,
        )
        .where(
            HouseholdFactModel.effective_to.is_not(None),
            HouseholdFactModel.effective_to < now,
        ),
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
    failed_integration_messages = await _scalar_count(
        session,
        select(func.count())
        .select_from(IntegrationMessageModel)
        .where(
            IntegrationMessageModel.processing_status
            == IntegrationProcessingStatus.FAILED
        ),
    )
    failed_referral_dispatches = await _scalar_count(
        session,
        select(func.count())
        .select_from(ReferralDispatchModel)
        .where(ReferralDispatchModel.status == "FAILED"),
    )
    failed_outbox_messages = await _scalar_count(
        session,
        select(func.count())
        .select_from(OutboxMessageModel)
        .where(
            OutboxMessageModel.published_at.is_(None),
            OutboxMessageModel.last_error.is_not(None),
        ),
    )
    integration_failures = (
        failed_integration_messages
        + failed_referral_dispatches
        + failed_outbox_messages
    )
    return DataHealthResponse(
        data=DataHealthData(
            missing_required_data=missing_required_data,
            unresolved_conflicts=disputed,
            incomplete_assessments=incomplete_assessments,
            stale_source_data=stale_source_data,
            integration_failures=integration_failures,
            pending_validation_facts=pending_validation,
            disputed_facts=disputed,
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

    async def diagnosis_decision_count(action: HumanDecisionAction) -> int:
        return await _scalar_count(
            session,
            select(func.count())
            .select_from(HumanDecisionModel)
            .where(
                HumanDecisionModel.action == action,
                HumanDecisionModel.decision_context
                == HumanDecisionContext.DIAGNOSIS,
            ),
        )

    async def runtime_event_count(
        event_type: OperationalRuntimeEventType,
    ) -> int:
        return await _scalar_count(
            session,
            select(func.count())
            .select_from(OperationalRuntimeEventModel)
            .where(
                OperationalRuntimeEventModel.event_type == event_type.value
            ),
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
    workflow_backlog = await _scalar_count(
        session,
        select(func.count())
        .select_from(WorkItemModel)
        .where(
            WorkItemModel.work_type.in_(
                (
                    WorkItemType.REFERRAL_FOLLOWUP,
                    WorkItemType.REASSESSMENT_DUE,
                    WorkItemType.REASSESSMENT,
                    WorkItemType.OUTCOME_REVIEW,
                )
            ),
            WorkItemModel.status.in_(
                (WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
            ),
        ),
    )
    ai_fallback_total = await _scalar_count(
        session,
        select(func.count())
        .select_from(WorkItemModel)
        .where(WorkItemModel.work_type == WorkItemType.AI_FALLBACK),
    )
    diagnosis_confirm_total = await diagnosis_decision_count(
        HumanDecisionAction.CONFIRM
    )
    diagnosis_modify_total = await diagnosis_decision_count(
        HumanDecisionAction.MODIFY
    )
    diagnosis_replace_total = await diagnosis_decision_count(
        HumanDecisionAction.REPLACE
    )
    diagnosis_reject_total = await diagnosis_decision_count(
        HumanDecisionAction.REJECT
    )
    diagnosis_defer_total = await diagnosis_decision_count(
        HumanDecisionAction.DEFER
    )
    schema_failures = await runtime_event_count(
        OperationalRuntimeEventType.AI_SCHEMA_FAILURE
    )
    inference_failures = await runtime_event_count(
        OperationalRuntimeEventType.AI_INFERENCE_FAILURE
    )
    routing_failures = await runtime_event_count(
        OperationalRuntimeEventType.AI_ROUTING_FAILURE
    )

    return MachineHealthResponse(
        data=MachineHealthData(
            diagnosis_confirm_total=diagnosis_confirm_total,
            diagnosis_modify_total=diagnosis_modify_total,
            diagnosis_replace_total=diagnosis_replace_total,
            schema_failures=schema_failures,
            ai_fallback_total=ai_fallback_total,
            inference_failures=inference_failures,
            workflow_backlog=workflow_backlog,
            routing_failures=routing_failures,
            ai_decisions_total=ai_decisions_total,
            human_confirm_total=diagnosis_confirm_total,
            human_modify_total=diagnosis_modify_total,
            human_replace_total=diagnosis_replace_total,
            human_reject_total=diagnosis_reject_total,
            human_defer_total=diagnosis_defer_total,
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



def _empowerment_distribution_data(
    value: VariableDistribution,
) -> PGORDistributionData:
    return PGORDistributionData(
        mean=value.mean,
        minimum=value.minimum,
        maximum=value.maximum,
    )


def _require_empowerment_unit_scope(
    context: AuthorizationContext,
) -> str:
    if context.unit_id is None:
        SECURITY_DENIALS.labels(
            boundary="organization_scope",
            reason="analytics_unit_scope_missing",
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ANALYTICS_UNIT_SCOPE_REQUIRED"},
        )
    return context.unit_id


@router.get(
    "/api/v1/admin/empowerment/overview",
    response_model=EmpowermentOverviewResponse,
)
async def get_empowerment_overview(
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.MANAGER, Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EmpowermentOverviewResponse:
    unit_id = _require_empowerment_unit_scope(context)
    overview = await SqlAlchemyEmpowermentOverviewRepository(
        session
    ).get_for_unit(unit_id=unit_id)

    return EmpowermentOverviewResponse(
        data=EmpowermentOverviewData(
            scope_unit_id=unit_id,
            household_count=overview.household_count,
            households_with_official_pgor=(
                overview.households_with_official_pgor
            ),
            p=_empowerment_distribution_data(overview.p),
            g=_empowerment_distribution_data(overview.g),
            o=_empowerment_distribution_data(overview.o),
            r=_empowerment_distribution_data(overview.r),
            e=_empowerment_distribution_data(overview.e),
            e_band_counts=overview.e_band_counts,
            bottleneck_counts=overview.bottleneck_counts,
            outcome_counts=overview.outcome_counts,
            unreviewed_outcomes=overview.unreviewed_outcomes,
            generated_at=datetime.now(UTC),
        )
    )
