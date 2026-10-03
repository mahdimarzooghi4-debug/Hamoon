from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.outcome.domain.entities import (
    HamoonOutcome,
    OutcomeInterpretationProposal,
)
from hamoon.domains.outcome.domain.errors import OutcomeVersionConflictError
from hamoon.domains.outcome.infrastructure.models import (
    HamoonOutcomeModel,
    OutcomeInterpretationProposalModel,
)


def _outcome(model: HamoonOutcomeModel) -> HamoonOutcome:
    return HamoonOutcome(
        id=model.id,
        household_id=model.household_id,
        intervention_id=model.intervention_id,
        referral_id=model.referral_id,
        provider_result_id=model.provider_result_id,
        pre_assessment_id=model.pre_assessment_id,
        post_assessment_id=model.post_assessment_id,
        pre_pgor_snapshot_id=model.pre_pgor_snapshot_id,
        post_pgor_snapshot_id=model.post_pgor_snapshot_id,
        status=model.status,
        classification=model.classification,
        observed_change_summary=model.observed_change_summary,
        p_delta=model.p_delta,
        g_delta=model.g_delta,
        o_delta=model.o_delta,
        r_delta=model.r_delta,
        e_delta=model.e_delta,
        confidence=model.confidence,
        assessed_at=model.assessed_at,
        assessed_by=model.assessed_by,
        methodology_version=model.methodology_version,
        version=model.version,
        latest_human_decision_id=model.latest_human_decision_id,
        reviewed_at=model.reviewed_at,
        reviewed_by=model.reviewed_by,
    )


class SqlAlchemyOutcomeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, outcome: HamoonOutcome) -> None:
        self._session.add(
            HamoonOutcomeModel(
                id=outcome.id,
                household_id=outcome.household_id,
                intervention_id=outcome.intervention_id,
                referral_id=outcome.referral_id,
                provider_result_id=outcome.provider_result_id,
                pre_assessment_id=outcome.pre_assessment_id,
                post_assessment_id=outcome.post_assessment_id,
                pre_pgor_snapshot_id=outcome.pre_pgor_snapshot_id,
                post_pgor_snapshot_id=outcome.post_pgor_snapshot_id,
                status=outcome.status,
                classification=outcome.classification,
                observed_change_summary=outcome.observed_change_summary,
                p_delta=outcome.p_delta,
                g_delta=outcome.g_delta,
                o_delta=outcome.o_delta,
                r_delta=outcome.r_delta,
                e_delta=outcome.e_delta,
                confidence=outcome.confidence,
                assessed_at=outcome.assessed_at,
                assessed_by=outcome.assessed_by,
                methodology_version=outcome.methodology_version,
                version=outcome.version,
                latest_human_decision_id=outcome.latest_human_decision_id,
                reviewed_at=outcome.reviewed_at,
                reviewed_by=outcome.reviewed_by,
            )
        )

    async def get(self, outcome_id: UUID) -> HamoonOutcome | None:
        model = await self._session.get(HamoonOutcomeModel, outcome_id)
        return None if model is None else _outcome(model)

    async def get_by_post_assessment(
        self,
        post_assessment_id: UUID,
    ) -> HamoonOutcome | None:
        result = await self._session.execute(
            select(HamoonOutcomeModel).where(
                HamoonOutcomeModel.post_assessment_id == post_assessment_id
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _outcome(model)

    async def update(
        self,
        outcome: HamoonOutcome,
        *,
        expected_version: int,
    ) -> None:
        result = await self._session.execute(
            select(HamoonOutcomeModel)
            .where(HamoonOutcomeModel.id == outcome.id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("OUTCOME_NOT_FOUND")
        if model.version != expected_version:
            raise OutcomeVersionConflictError("Outcome version changed.")
        model.status = outcome.status
        model.classification = outcome.classification
        model.observed_change_summary = outcome.observed_change_summary
        model.version = outcome.version
        model.latest_human_decision_id = outcome.latest_human_decision_id
        model.reviewed_at = outcome.reviewed_at
        model.reviewed_by = outcome.reviewed_by



class SqlAlchemyOutcomeInterpretationProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _hydrate(
        model: OutcomeInterpretationProposalModel,
    ) -> OutcomeInterpretationProposal:
        return OutcomeInterpretationProposal(
            id=model.id,
            outcome_id=model.outcome_id,
            ai_decision_id=model.ai_decision_id,
            created_at=model.created_at,
        )

    async def add(self, proposal: OutcomeInterpretationProposal) -> None:
        self._session.add(
            OutcomeInterpretationProposalModel(
                id=proposal.id,
                outcome_id=proposal.outcome_id,
                ai_decision_id=proposal.ai_decision_id,
                created_at=proposal.created_at,
            )
        )

    async def get(
        self,
        proposal_id: UUID,
    ) -> OutcomeInterpretationProposal | None:
        model = await self._session.get(
            OutcomeInterpretationProposalModel,
            proposal_id,
        )
        return None if model is None else self._hydrate(model)

    async def get_by_outcome(
        self,
        outcome_id: UUID,
    ) -> OutcomeInterpretationProposal | None:
        result = await self._session.execute(
            select(OutcomeInterpretationProposalModel).where(
                OutcomeInterpretationProposalModel.outcome_id == outcome_id
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._hydrate(model)
