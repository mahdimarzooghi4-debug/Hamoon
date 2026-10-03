from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import JsonValue

from hamoon.domains.assessment.domain.entities import AssessmentType
from hamoon.domains.assessment.ports.repositories import AssessmentRepository
from hamoon.domains.intelligence.domain.decisions import (
    HumanDecision,
    HumanDecisionAction,
    HumanDecisionContext,
    LearningSignal,
    LearningSignalQuality,
    LearningSignalType,
)
from hamoon.domains.intelligence.ports.repositories import (
    AIDecisionRepository,
    DecisionTraceRepository,
    HumanDecisionRepository,
    LearningSignalRepository,
)
from hamoon.domains.intervention.ports.repositories import InterventionRepository
from hamoon.domains.outcome.application.commands import (
    PrepareOutcomeCommand,
    ReviewOutcomeCommand,
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
from hamoon.domains.outcome.ports.repositories import (
    OutcomeInterpretationProposalRepository,
    OutcomeRepository,
)
from hamoon.domains.pgor.domain.engine import PGORSnapshotStatus
from hamoon.domains.pgor.ports.repositories import PGORSnapshotRepository
from hamoon.domains.provider_result.ports.repositories import ProviderResultRepository
from hamoon.domains.referral.ports.repositories import ReferralRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder

OUTCOME_METHODOLOGY_VERSION = "observed-pgor-delta-v1"

_REVIEWABLE_CLASSIFICATIONS = {
    OutcomeClassification.GOAL_ACHIEVED,
    OutcomeClassification.PROGRESS,
    OutcomeClassification.NO_SIGNIFICANT_CHANGE,
    OutcomeClassification.REGRESSION,
}


def _delta(post: Decimal, pre: Decimal) -> Decimal:
    return post - pre


class PrepareOutcomeHandler:
    def __init__(
        self,
        *,
        interventions: InterventionRepository,
        assessments: AssessmentRepository,
        snapshots: PGORSnapshotRepository,
        provider_results: ProviderResultRepository,
        referrals: ReferralRepository,
        outcomes: OutcomeRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._interventions = interventions
        self._assessments = assessments
        self._snapshots = snapshots
        self._provider_results = provider_results
        self._referrals = referrals
        self._outcomes = outcomes
        self._events = events
        self._audits = audits

    async def handle(self, command: PrepareOutcomeCommand) -> HamoonOutcome:
        existing = await self._outcomes.get_by_post_assessment(
            command.post_assessment_id
        )
        if existing is not None:
            if (
                existing.intervention_id != command.intervention_id
                or existing.provider_result_id != command.provider_result_id
                or existing.pre_assessment_id != command.pre_assessment_id
            ):
                raise OutcomePreparationError(
                    "POST_ASSESSMENT_ALREADY_USED_BY_DIFFERENT_OUTCOME"
                )
            return existing

        intervention = await self._interventions.get(command.intervention_id)
        if intervention is None:
            raise OutcomePreparationError("INTERVENTION_NOT_FOUND")

        pre_assessment = await self._assessments.get(command.pre_assessment_id)
        post_assessment = await self._assessments.get(command.post_assessment_id)
        if pre_assessment is None or post_assessment is None:
            raise OutcomePreparationError("ASSESSMENT_NOT_FOUND")
        if (
            pre_assessment.household_id != intervention.household_id
            or post_assessment.household_id != intervention.household_id
        ):
            raise OutcomePreparationError("ASSESSMENT_HOUSEHOLD_MISMATCH")
        if post_assessment.assessment_type not in {
            AssessmentType.REASSESSMENT,
            AssessmentType.OUTCOME_REASSESSMENT,
        }:
            raise OutcomePreparationError("POST_ASSESSMENT_NOT_REASSESSMENT")
        if (
            post_assessment.intervention_id is not None
            and post_assessment.intervention_id != intervention.id
        ):
            raise OutcomePreparationError("POST_ASSESSMENT_INTERVENTION_MISMATCH")

        pre = await self._snapshots.get_official_by_assessment(pre_assessment.id)
        post = await self._snapshots.get_official_by_assessment(post_assessment.id)
        if pre is None or post is None:
            raise OutcomePreparationError("OFFICIAL_PGOR_SNAPSHOT_REQUIRED")
        if (
            pre.status is not PGORSnapshotStatus.OFFICIAL
            or post.status is not PGORSnapshotStatus.OFFICIAL
        ):
            raise OutcomePreparationError("OFFICIAL_PGOR_SNAPSHOT_REQUIRED")

        provider_result = await self._provider_results.get(command.provider_result_id)
        if provider_result is None:
            raise OutcomePreparationError("PROVIDER_RESULT_NOT_FOUND")
        referral = await self._referrals.get(provider_result.referral_id)
        if (
            referral is None
            or referral.household_id != intervention.household_id
            or referral.intervention_id != intervention.id
        ):
            raise OutcomePreparationError("PROVIDER_RESULT_INTERVENTION_MISMATCH")

        p_delta = _delta(post.p, pre.p)
        g_delta = _delta(post.g, pre.g)
        o_delta = _delta(post.o, pre.o)
        r_delta = _delta(post.r, pre.r)
        e_delta = _delta(post.e, pre.e)
        summary = (
            "Observed PGOR change between official pre/post snapshots; "
            f"ΔP={p_delta}, ΔG={g_delta}, ΔO={o_delta}, "
            f"ΔR={r_delta}, ΔE={e_delta}. "
            "This comparison does not by itself establish causality."
        )
        now = datetime.now(UTC)
        outcome = HamoonOutcome(
            id=uuid4(),
            household_id=intervention.household_id,
            intervention_id=intervention.id,
            referral_id=referral.id,
            provider_result_id=provider_result.id,
            pre_assessment_id=pre_assessment.id,
            post_assessment_id=post_assessment.id,
            pre_pgor_snapshot_id=pre.id,
            post_pgor_snapshot_id=post.id,
            status=OutcomeStatus.UNDER_REVIEW,
            classification=None,
            observed_change_summary=summary,
            p_delta=p_delta,
            g_delta=g_delta,
            o_delta=o_delta,
            r_delta=r_delta,
            e_delta=e_delta,
            confidence=None,
            assessed_at=now,
            assessed_by=command.actor_id,
            methodology_version=OUTCOME_METHODOLOGY_VERSION,
            version=1,
        )
        await self._outcomes.add(outcome)
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="OutcomePrepared",
                event_version=1,
                aggregate_type="HAMOON_OUTCOME",
                aggregate_id=outcome.id,
                aggregate_version=outcome.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "outcome_id": str(outcome.id),
                    "intervention_id": str(outcome.intervention_id),
                    "pre_pgor_snapshot_id": str(outcome.pre_pgor_snapshot_id),
                    "post_pgor_snapshot_id": str(outcome.post_pgor_snapshot_id),
                    "provider_result_id": str(provider_result.id),
                    "methodology_version": outcome.methodology_version,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="outcome.prepare",
                resource_type="HAMOON_OUTCOME",
                resource_id=outcome.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="OUTCOME_MEASUREMENT",
                metadata={
                    "event_id": str(event_id),
                    "intervention_id": str(outcome.intervention_id),
                    "provider_result_id": str(provider_result.id),
                    "pre_pgor_snapshot_id": str(pre.id),
                    "post_pgor_snapshot_id": str(post.id),
                    "methodology_version": outcome.methodology_version,
                },
            )
        )
        return outcome


class ReviewOutcomeHandler:
    def __init__(
        self,
        *,
        outcomes: OutcomeRepository,
        human_decisions: HumanDecisionRepository,
        learning_signals: LearningSignalRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
        proposals: OutcomeInterpretationProposalRepository | None = None,
        ai_decisions: AIDecisionRepository | None = None,
        traces: DecisionTraceRepository | None = None,
    ) -> None:
        self._outcomes = outcomes
        self._human_decisions = human_decisions
        self._learning_signals = learning_signals
        self._events = events
        self._audits = audits
        self._proposals = proposals
        self._ai_decisions = ai_decisions
        self._traces = traces

    async def handle(
        self,
        command: ReviewOutcomeCommand,
        *,
        action: HumanDecisionAction,
        target_status: OutcomeStatus,
    ) -> tuple[HamoonOutcome, HumanDecision, LearningSignal]:
        outcome = await self._outcomes.get(command.outcome_id)
        if outcome is None:
            raise OutcomeReviewError("OUTCOME_NOT_FOUND")
        if outcome.version != command.expected_version:
            raise OutcomeVersionConflictError("Outcome version changed.")

        if target_status in {OutcomeStatus.CONFIRMED, OutcomeStatus.MODIFIED}:
            if command.classification not in _REVIEWABLE_CLASSIFICATIONS:
                raise OutcomeReviewError("OUTCOME_CLASSIFICATION_INVALID_FOR_REVIEW")
        elif target_status is OutcomeStatus.NEEDS_MORE_TIME:
            if command.classification is not OutcomeClassification.NEEDS_MORE_TIME:
                raise OutcomeReviewError("OUTCOME_CLASSIFICATION_MISMATCH")
        elif target_status is OutcomeStatus.NEEDS_MORE_DATA:
            if command.classification is not OutcomeClassification.NEEDS_MORE_DATA:
                raise OutcomeReviewError("OUTCOME_CLASSIFICATION_MISMATCH")

        if action is HumanDecisionAction.MODIFY and not (
            command.reason_code or command.reason_text
        ):
            raise OutcomeReviewError("OUTCOME_MODIFICATION_REASON_REQUIRED")

        ai_decision_id = None
        machine_summary: str | None = None
        if self._proposals is not None:
            proposal = await self._proposals.get_by_outcome(outcome.id)
            if proposal is not None:
                ai_decision_id = proposal.ai_decision_id
                if self._ai_decisions is None:
                    raise OutcomeReviewError("AI_DECISION_REPOSITORY_REQUIRED")
                ai_decision = await self._ai_decisions.get(proposal.ai_decision_id)
                if ai_decision is None:
                    raise OutcomeReviewError("OUTCOME_AI_DECISION_NOT_FOUND")
                raw_classification = ai_decision.structured_output.get("classification")
                raw_summary = ai_decision.structured_output.get(
                    "observed_change_summary"
                )
                if not isinstance(raw_classification, str) or not isinstance(
                    raw_summary,
                    str,
                ):
                    raise OutcomeReviewError("OUTCOME_AI_PROPOSAL_INVALID")
                machine_summary = raw_summary
                if action is HumanDecisionAction.CONFIRM:
                    if raw_classification != command.classification.value:
                        raise OutcomeReviewError(
                            "OUTCOME_CONFIRM_MUST_MATCH_AI_PROPOSAL"
                        )
                    if (
                        command.observed_change_summary is not None
                        and command.observed_change_summary.strip() != raw_summary
                    ):
                        raise OutcomeReviewError(
                            "OUTCOME_CONFIRM_MUST_MATCH_AI_PROPOSAL"
                        )

        summary = (
            command.observed_change_summary.strip()
            if command.observed_change_summary
            else machine_summary or outcome.observed_change_summary
        )
        if not summary:
            raise OutcomeReviewError("OUTCOME_SUMMARY_REQUIRED")

        now = datetime.now(UTC)
        human_id = uuid4()
        try:
            updated = outcome.review(
                status=target_status,
                classification=command.classification,
                summary=summary,
                human_decision_id=human_id,
                actor_id=command.actor_id,
                decided_at=now,
            )
        except ValueError as exc:
            raise OutcomeReviewError(str(exc)) from exc

        accepted_payload: dict[str, JsonValue] = {
            "outcome_id": str(outcome.id),
            "classification": command.classification.value,
            "observed_change_summary": summary,
            "methodology_version": outcome.methodology_version,
            "p_delta": str(outcome.p_delta),
            "g_delta": str(outcome.g_delta),
            "o_delta": str(outcome.o_delta),
            "r_delta": str(outcome.r_delta),
            "e_delta": str(outcome.e_delta),
            "causal_claim": False,
        }
        human = HumanDecision(
            id=human_id,
            household_id=outcome.household_id,
            ai_decision_id=ai_decision_id,
            actor_id=command.actor_id,
            action=action,
            reason_code=command.reason_code,
            reason_text=command.reason_text,
            accepted_payload=accepted_payload,
            modified_payload=(
                accepted_payload if action is HumanDecisionAction.MODIFY else None
            ),
            decided_at=now,
            decision_context=HumanDecisionContext.OUTCOME,
            outcome_id=outcome.id,
        )
        signal = LearningSignal(
            id=uuid4(),
            household_id=outcome.household_id,
            signal_type=LearningSignalType.OUTCOME_OBSERVED,
            ai_decision_id=ai_decision_id,
            human_decision_id=human.id,
            diagnosis_id=None,
            signal_label=command.classification.value,
            quality_status=LearningSignalQuality.RAW,
            created_at=now,
            created_by=command.actor_id,
            intervention_id=outcome.intervention_id,
            provider_result_id=outcome.provider_result_id,
            outcome_id=outcome.id,
        )
        await self._human_decisions.add(human)
        await self._outcomes.update(updated, expected_version=command.expected_version)
        await self._learning_signals.add(signal)
        if ai_decision_id is not None and self._traces is not None:
            await self._traces.attach_human_decision(
                ai_decision_id=ai_decision_id,
                human_decision_id=human.id,
                closed_at=now,
            )

        event_type = {
            OutcomeStatus.CONFIRMED: "OutcomeConfirmed",
            OutcomeStatus.MODIFIED: "OutcomeModified",
            OutcomeStatus.NEEDS_MORE_TIME: "OutcomeNeedsMoreTime",
            OutcomeStatus.NEEDS_MORE_DATA: "OutcomeNeedsMoreData",
        }[target_status]
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type=event_type,
                event_version=1,
                aggregate_type="HAMOON_OUTCOME",
                aggregate_id=outcome.id,
                aggregate_version=updated.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "outcome_id": str(outcome.id),
                    "classification": command.classification.value,
                    "p_delta": str(outcome.p_delta),
                    "g_delta": str(outcome.g_delta),
                    "o_delta": str(outcome.o_delta),
                    "r_delta": str(outcome.r_delta),
                    "e_delta": str(outcome.e_delta),
                    "reviewed_by": str(command.actor_id),
                    "human_decision_id": str(human.id),
                    "ai_decision_id": (
                        None if ai_decision_id is None else str(ai_decision_id)
                    ),
                    "learning_signal_id": str(signal.id),
                    "causal_claim": False,
                },
            )
        )
        await self._events.record(
            DomainEventRecord(
                event_id=uuid4(),
                event_type="LearningSignalCreated",
                event_version=1,
                aggregate_type="LEARNING_SIGNAL",
                aggregate_id=signal.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=str(event_id),
                payload={
                    "learning_signal_id": str(signal.id),
                    "household_id": str(signal.household_id),
                    "signal_type": signal.signal_type.value,
                    "human_decision_id": str(signal.human_decision_id),
                    "ai_decision_id": (
                        None
                        if signal.ai_decision_id is None
                        else str(signal.ai_decision_id)
                    ),
                    "provider_result_id": (
                        None
                        if signal.provider_result_id is None
                        else str(signal.provider_result_id)
                    ),
                    "outcome_id": str(outcome.id),
                    "quality_status": signal.quality_status.value,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="outcome.review",
                resource_type="HAMOON_OUTCOME",
                resource_id=outcome.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="OUTCOME_REVIEW",
                metadata={
                    "event_id": str(event_id),
                    "human_decision_id": str(human.id),
                    "ai_decision_id": (
                        None if ai_decision_id is None else str(ai_decision_id)
                    ),
                    "learning_signal_id": str(signal.id),
                    "classification": command.classification.value,
                    "version": updated.version,
                    "causal_claim": False,
                },
            )
        )
        return updated, human, signal
