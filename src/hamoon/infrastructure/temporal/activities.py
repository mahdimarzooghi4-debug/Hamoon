from temporalio import activity
from temporalio.exceptions import ApplicationError

from hamoon.app.config.settings import get_settings
from hamoon.domains.assessment.infrastructure.repositories import (
    SqlAlchemyAssessmentRepository,
)
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyAIDecisionRepository,
    SqlAlchemyDecisionTraceRepository,
    SqlAlchemyFeaturePackageRepository,
)
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.operations.application.handlers import (
    CreateOutcomeReviewWorkItemHandler,
    MaterializeReassessmentWorkItemHandler,
)
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyReassessmentPlanRepository,
    SqlAlchemyWorkItemRepository,
)
from hamoon.domains.outcome.application.commands import PrepareOutcomeCommand
from hamoon.domains.outcome.application.handlers import PrepareOutcomeHandler
from hamoon.domains.outcome.application.intelligence import (
    GenerateOutcomeInterpretationCommand,
    GenerateOutcomeInterpretationHandler,
)
from hamoon.domains.outcome.domain.errors import (
    OutcomeInterpretationError,
    OutcomePreparationError,
)
from hamoon.domains.outcome.infrastructure.repositories import (
    SqlAlchemyOutcomeInterpretationProposalRepository,
    SqlAlchemyOutcomeRepository,
)
from hamoon.domains.pgor.infrastructure.repositories import (
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
from hamoon.infrastructure.ai.outcome_factory import (
    OutcomeAIRuntimeConfigurationError,
    build_outcome_ai_client,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import session_factory
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder
from hamoon.infrastructure.temporal.contracts import (
    GenerateOutcomeAIInput,
    MaterializeOutcomeReviewInput,
    MaterializeReassessmentInput,
    PrepareOutcomeInput,
)


@activity.defn(name="materialize_reassessment_work_item")
async def materialize_reassessment_work_item(
    data: MaterializeReassessmentInput,
) -> str:
    async with session_factory() as session:
        async with session.begin():
            item = await MaterializeReassessmentWorkItemHandler(
                plans=SqlAlchemyReassessmentPlanRepository(session),
                work_items=SqlAlchemyWorkItemRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                plan_id=data.plan_id,
                actor_id=data.actor_id,
                request_id=activity.info().activity_id,
                correlation_id=data.correlation_id,
            )
    return str(item.id)


@activity.defn(name="prepare_reassessment_outcome")
async def prepare_reassessment_outcome(data: PrepareOutcomeInput) -> str:
    async with session_factory() as session:
        plans = SqlAlchemyReassessmentPlanRepository(session)
        plan = await plans.get(data.plan_id)
        if plan is None:
            raise ApplicationError(
                "REASSESSMENT_PLAN_NOT_FOUND",
                non_retryable=True,
            )
        if (
            plan.post_assessment_id != data.post_assessment_id
            or plan.post_pgor_snapshot_id != data.post_snapshot_id
        ):
            raise ApplicationError(
                "REASSESSMENT_POST_PGOR_MISMATCH",
                non_retryable=True,
            )
        if plan.outcome_id is not None:
            return str(plan.outcome_id)

        prescriptions = SqlAlchemyPrescriptionRepository(session)
        item = await prescriptions.get_item_by_id(plan.prescription_item_id)
        if item is None:
            raise ApplicationError("PRESCRIPTION_ITEM_NOT_FOUND", non_retryable=True)
        prescription = await prescriptions.get(item.prescription_id)
        if prescription is None:
            raise ApplicationError("PRESCRIPTION_NOT_FOUND", non_retryable=True)
        pre_snapshot = await SqlAlchemyPGORSnapshotRepository(session).get(
            prescription.pgor_snapshot_id
        )
        if pre_snapshot is None:
            raise ApplicationError("PRE_PGOR_SNAPSHOT_NOT_FOUND", non_retryable=True)
        await session.rollback()

        try:
            async with session.begin():
                outcome = await PrepareOutcomeHandler(
                    interventions=SqlAlchemyInterventionRepository(session),
                    assessments=SqlAlchemyAssessmentRepository(session),
                    snapshots=SqlAlchemyPGORSnapshotRepository(session),
                    provider_results=SqlAlchemyProviderResultRepository(session),
                    referrals=SqlAlchemyReferralRepository(session),
                    outcomes=SqlAlchemyOutcomeRepository(session),
                    events=SqlAlchemyDomainEventRecorder(session),
                    audits=SqlAlchemyAuditRecorder(session),
                ).handle(
                    PrepareOutcomeCommand(
                        intervention_id=plan.intervention_id,
                        pre_assessment_id=pre_snapshot.assessment_id,
                        post_assessment_id=data.post_assessment_id,
                        provider_result_id=plan.provider_result_id,
                        actor_id=data.actor_id,
                        request_id=activity.info().activity_id,
                        correlation_id=data.correlation_id,
                    )
                )
        except OutcomePreparationError as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc
    return str(outcome.id)


@activity.defn(name="generate_reassessment_outcome_ai")
async def generate_reassessment_outcome_ai(
    data: GenerateOutcomeAIInput,
) -> str:
    settings = get_settings()

    async with session_factory() as session:
        proposal = await SqlAlchemyOutcomeInterpretationProposalRepository(
            session
        ).get_by_outcome(data.outcome_id)
        if proposal is not None:
            return str(proposal.ai_decision_id)
        try:
            ai_client = await build_outcome_ai_client(
                session=session,
                settings=settings,
            )
        except OutcomeAIRuntimeConfigurationError as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc
        await session.rollback()

        command = GenerateOutcomeInterpretationCommand(
            outcome_id=data.outcome_id,
            actor_id=data.actor_id,
            request_id=activity.info().activity_id,
            correlation_id=data.correlation_id,
        )
        async with session.begin():
            handler = GenerateOutcomeInterpretationHandler(
                outcomes=SqlAlchemyOutcomeRepository(session),
                proposals=SqlAlchemyOutcomeInterpretationProposalRepository(session),
                snapshots=SqlAlchemyPGORSnapshotRepository(session),
                interventions=SqlAlchemyInterventionRepository(session),
                provider_results=SqlAlchemyProviderResultRepository(session),
                feature_packages=SqlAlchemyFeaturePackageRepository(session),
                ai_decisions=SqlAlchemyAIDecisionRepository(session),
                traces=SqlAlchemyDecisionTraceRepository(session),
                ai_client=ai_client,
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            )
            prepared = await handler.prepare(command)

        try:
            result = await handler.infer(
                prepared=prepared,
                correlation_id=data.correlation_id,
            )
        except OutcomeInterpretationError as exc:
            code = str(exc)
            raise ApplicationError(
                code,
                non_retryable=code != "AI_PROVIDER_UNAVAILABLE",
            ) from exc

        async with session.begin():
            persist_handler = GenerateOutcomeInterpretationHandler(
                outcomes=SqlAlchemyOutcomeRepository(session),
                proposals=SqlAlchemyOutcomeInterpretationProposalRepository(session),
                snapshots=SqlAlchemyPGORSnapshotRepository(session),
                interventions=SqlAlchemyInterventionRepository(session),
                provider_results=SqlAlchemyProviderResultRepository(session),
                feature_packages=SqlAlchemyFeaturePackageRepository(session),
                ai_decisions=SqlAlchemyAIDecisionRepository(session),
                traces=SqlAlchemyDecisionTraceRepository(session),
                ai_client=ai_client,
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            )
            proposal, _decision = await persist_handler.persist(
                command=command,
                prepared=prepared,
                result=result,
            )
    return str(proposal.ai_decision_id)


@activity.defn(name="materialize_outcome_review_work_item")
async def materialize_outcome_review_work_item(
    data: MaterializeOutcomeReviewInput,
) -> str:
    async with session_factory() as session:
        async with session.begin():
            item = await CreateOutcomeReviewWorkItemHandler(
                plans=SqlAlchemyReassessmentPlanRepository(session),
                work_items=SqlAlchemyWorkItemRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                plan_id=data.plan_id,
                outcome_id=data.outcome_id,
                actor_id=data.actor_id,
                request_id=activity.info().activity_id,
                correlation_id=data.correlation_id,
            )
    return str(item.id)
