from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.config.settings import Settings, get_settings
from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyAIDecisionRepository,
    SqlAlchemyDecisionTraceRepository,
    SqlAlchemyFeaturePackageRepository,
)
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.outcome.api.schemas import (
    GenerateOutcomeInterpretationData,
    GenerateOutcomeInterpretationResponse,
    OutcomeInterpretationData,
    OutcomeInterpretationResponse,
)
from hamoon.domains.outcome.application.intelligence import (
    GenerateOutcomeInterpretationCommand,
    GenerateOutcomeInterpretationHandler,
)
from hamoon.domains.outcome.domain.errors import OutcomeInterpretationError
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
from hamoon.infrastructure.ai.outcome_factory import (
    OutcomeAIRuntimeConfigurationError,
    build_outcome_ai_client,
)
from hamoon.infrastructure.ai.outcome_runtime import GatewayOutcomeAIClient
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["outcome-intelligence"])


async def _resolve_ai_client(
    *,
    session: AsyncSession,
    settings: Settings,
) -> GatewayOutcomeAIClient:
    try:
        return await build_outcome_ai_client(
            session=session,
            settings=settings,
        )
    except OutcomeAIRuntimeConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": str(exc)},
        ) from exc


@router.post(
    "/api/v1/outcomes/{outcome_id}/interpretations/generate",
    response_model=GenerateOutcomeInterpretationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_outcome_interpretation(
    outcome_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GenerateOutcomeInterpretationResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    outcomes = SqlAlchemyOutcomeRepository(session)
    command = GenerateOutcomeInterpretationCommand(
        outcome_id=outcome_id,
        actor_id=context.actor_id,
        request_id=request_id,
        correlation_id=correlation_id,
    )
    try:
        async with session.begin():
            outcome = await outcomes.get(outcome_id)
            if outcome is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "RESOURCE_NOT_FOUND"},
                )
            await require_household_assignment(
                session=session,
                context=context,
                household_id=outcome.household_id,
            )
            ai_client = await _resolve_ai_client(
                session=session,
                settings=settings,
            )
            handler = GenerateOutcomeInterpretationHandler(
                outcomes=outcomes,
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

        result = await handler.infer(
            prepared=prepared,
            correlation_id=correlation_id,
        )

        async with session.begin():
            proposal, ai_decision = await handler.persist(
                command=command,
                prepared=prepared,
                result=result,
            )
    except OutcomeInterpretationError as exc:
        code = str(exc)
        http_status = (
            status.HTTP_409_CONFLICT
            if code == "OUTCOME_INTERPRETATION_ALREADY_EXISTS"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=http_status, detail={"code": code}) from exc

    return GenerateOutcomeInterpretationResponse(
        data=GenerateOutcomeInterpretationData(
            proposal_id=proposal.id,
            outcome_id=proposal.outcome_id,
            ai_decision_id=proposal.ai_decision_id,
            trace_id=ai_decision.trace_id,
        )
    )


@router.get(
    "/api/v1/outcomes/{outcome_id}/interpretation",
    response_model=OutcomeInterpretationResponse,
)
async def get_outcome_interpretation(
    outcome_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OutcomeInterpretationResponse:
    outcome = await SqlAlchemyOutcomeRepository(session).get(outcome_id)
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=outcome.household_id,
    )
    proposal = await SqlAlchemyOutcomeInterpretationProposalRepository(
        session
    ).get_by_outcome(outcome_id)
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    ai_decision = await SqlAlchemyAIDecisionRepository(session).get(
        proposal.ai_decision_id
    )
    if ai_decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    return OutcomeInterpretationResponse(
        data=OutcomeInterpretationData(
            proposal_id=proposal.id,
            outcome_id=proposal.outcome_id,
            ai_decision_id=ai_decision.id,
            feature_package_id=ai_decision.feature_package_id,
            trace_id=ai_decision.trace_id,
            model_alias=ai_decision.model_alias,
            routing_policy_version=ai_decision.routing_policy_version,
            prompt_policy_version=ai_decision.prompt_policy_version,
            output_schema_version=ai_decision.output_schema_version,
            machine_proposal=ai_decision.structured_output,
            created_at=proposal.created_at,
        )
    )
