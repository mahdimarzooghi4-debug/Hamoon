from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import JsonValue

from hamoon.domains.family_data.ports.repositories import AcceptedStateRepository
from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionStatus,
    AIDecisionType,
    AIExecutionResult,
    DecisionTrace,
)
from hamoon.domains.intelligence.domain.entities import (
    FeaturePackage,
    FeaturePackageType,
    FeatureValue,
)
from hamoon.domains.intelligence.ports.repositories import (
    AIDecisionRepository,
    DecisionTraceRepository,
    FeaturePackageRepository,
)
from hamoon.domains.intervention.ports.repositories import InterventionRepository
from hamoon.domains.outcome.domain.entities import (
    OutcomeInterpretationProposal,
    OutcomeStatus,
)
from hamoon.domains.outcome.domain.errors import OutcomeInterpretationError
from hamoon.domains.outcome.ports.ai import OutcomeAIClient
from hamoon.domains.outcome.ports.repositories import (
    OutcomeInterpretationProposalRepository,
    OutcomeRepository,
)
from hamoon.domains.pgor.domain.engine import PGORSnapshotStatus
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.pgor.ports.repositories import PGORSnapshotRepository
from hamoon.domains.provider_result.ports.repositories import ProviderResultRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder

OUTCOME_FEATURE_SCHEMA_VERSION = "outcome-input-v1"


@dataclass(frozen=True, slots=True)
class GenerateOutcomeInterpretationCommand:
    outcome_id: UUID
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class PreparedOutcomeInterpretation:
    outcome_id: UUID
    household_id: UUID
    intervention_id: UUID
    referral_id: UUID | None
    provider_result_id: UUID | None
    post_snapshot: PGORSnapshot
    feature_package: FeaturePackage
    household_context_version: int | None = None


def _validate_output(
    *,
    output: dict[str, JsonValue],
    package: FeaturePackage,
) -> None:
    if output.get("causal_claim") is not False:
        raise OutcomeInterpretationError("AI_CAUSAL_CLAIM_NOT_ALLOWED")
    refs = output.get("supporting_feature_refs")
    if not isinstance(refs, list) or not refs:
        raise OutcomeInterpretationError("AI_OUTCOME_GROUNDING_REQUIRED")
    allowed = set(package.provider_payload().keys())
    for ref in refs:
        if not isinstance(ref, str) or ref not in allowed:
            raise OutcomeInterpretationError("AI_OUTCOME_GROUNDING_INVALID")
    flags = output.get("review_flags")
    if not isinstance(flags, list) or "HUMAN_REVIEW_REQUIRED" not in flags:
        raise OutcomeInterpretationError("AI_HUMAN_REVIEW_FLAG_REQUIRED")


class GenerateOutcomeInterpretationHandler:
    def __init__(
        self,
        *,
        outcomes: OutcomeRepository,
        proposals: OutcomeInterpretationProposalRepository,
        snapshots: PGORSnapshotRepository,
        interventions: InterventionRepository,
        provider_results: ProviderResultRepository,
        feature_packages: FeaturePackageRepository,
        ai_decisions: AIDecisionRepository,
        traces: DecisionTraceRepository,
        ai_client: OutcomeAIClient,
        accepted_state: AcceptedStateRepository | None = None,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._outcomes = outcomes
        self._proposals = proposals
        self._snapshots = snapshots
        self._interventions = interventions
        self._provider_results = provider_results
        self._feature_packages = feature_packages
        self._ai_decisions = ai_decisions
        self._traces = traces
        self._ai_client = ai_client
        self._accepted_state = accepted_state
        self._events = events
        self._audits = audits

    async def prepare(
        self,
        command: GenerateOutcomeInterpretationCommand,
    ) -> PreparedOutcomeInterpretation:
        outcome = await self._outcomes.get(command.outcome_id)
        if outcome is None:
            raise OutcomeInterpretationError("OUTCOME_NOT_FOUND")
        if outcome.status is not OutcomeStatus.UNDER_REVIEW:
            raise OutcomeInterpretationError("OUTCOME_NOT_UNDER_REVIEW")
        if await self._proposals.get_by_outcome(outcome.id) is not None:
            raise OutcomeInterpretationError("OUTCOME_INTERPRETATION_ALREADY_EXISTS")

        pre = await self._snapshots.get(outcome.pre_pgor_snapshot_id)
        post = await self._snapshots.get(outcome.post_pgor_snapshot_id)
        if (
            pre is None
            or post is None
            or pre.status is not PGORSnapshotStatus.OFFICIAL
            or post.status is not PGORSnapshotStatus.OFFICIAL
        ):
            raise OutcomeInterpretationError("OFFICIAL_PGOR_SNAPSHOTS_REQUIRED")

        intervention = await self._interventions.get(outcome.intervention_id)
        if intervention is None:
            raise OutcomeInterpretationError("INTERVENTION_NOT_FOUND")

        provider_result_type: str | None = None
        provider_result_status: str | None = None
        if outcome.provider_result_id is not None:
            provider_result = await self._provider_results.get(
                outcome.provider_result_id
            )
            if provider_result is None:
                raise OutcomeInterpretationError("PROVIDER_RESULT_NOT_FOUND")
            provider_result_type = provider_result.result_type
            provider_result_status = provider_result.result_status

        existing = await self._feature_packages.get_by_snapshot(
            snapshot_id=post.id,
            schema_version=OUTCOME_FEATURE_SCHEMA_VERSION,
        )
        if existing is not None:
            household_context_version = (
                await self._accepted_state.context_version(outcome.household_id)
                if self._accepted_state is not None
                else None
            )
            return PreparedOutcomeInterpretation(
                outcome_id=outcome.id,
                household_id=outcome.household_id,
                intervention_id=outcome.intervention_id,
                referral_id=outcome.referral_id,
                provider_result_id=outcome.provider_result_id,
                post_snapshot=post,
                feature_package=existing,
                household_context_version=household_context_version,
            )

        provider_ref = (
            f"provider_result:{outcome.provider_result_id}"
            if outcome.provider_result_id is not None
            else f"outcome:{outcome.id}"
        )
        values = (
            FeatureValue("pgor.pre.P", str(pre.p), (f"pgor_snapshot:{pre.id}",)),
            FeatureValue("pgor.pre.G", str(pre.g), (f"pgor_snapshot:{pre.id}",)),
            FeatureValue("pgor.pre.O", str(pre.o), (f"pgor_snapshot:{pre.id}",)),
            FeatureValue("pgor.pre.R", str(pre.r), (f"pgor_snapshot:{pre.id}",)),
            FeatureValue("pgor.pre.E", str(pre.e), (f"pgor_snapshot:{pre.id}",)),
            FeatureValue("pgor.post.P", str(post.p), (f"pgor_snapshot:{post.id}",)),
            FeatureValue("pgor.post.G", str(post.g), (f"pgor_snapshot:{post.id}",)),
            FeatureValue("pgor.post.O", str(post.o), (f"pgor_snapshot:{post.id}",)),
            FeatureValue("pgor.post.R", str(post.r), (f"pgor_snapshot:{post.id}",)),
            FeatureValue("pgor.post.E", str(post.e), (f"pgor_snapshot:{post.id}",)),
            FeatureValue("pgor.delta.P", str(outcome.p_delta), (f"outcome:{outcome.id}",)),
            FeatureValue("pgor.delta.G", str(outcome.g_delta), (f"outcome:{outcome.id}",)),
            FeatureValue("pgor.delta.O", str(outcome.o_delta), (f"outcome:{outcome.id}",)),
            FeatureValue("pgor.delta.R", str(outcome.r_delta), (f"outcome:{outcome.id}",)),
            FeatureValue("pgor.delta.E", str(outcome.e_delta), (f"outcome:{outcome.id}",)),
            FeatureValue(
                "intervention.type",
                intervention.intervention_type.value,
                (f"intervention:{intervention.id}",),
            ),
            FeatureValue(
                "intervention.target_variable",
                intervention.target_pgor_variable.value,
                (f"intervention:{intervention.id}",),
            ),
            FeatureValue(
                "provider_result.type",
                provider_result_type,
                (provider_ref,),
            ),
            FeatureValue(
                "provider_result.status",
                provider_result_status,
                (provider_ref,),
            ),
            FeatureValue(
                "outcome.methodology_version",
                outcome.methodology_version,
                (f"outcome:{outcome.id}",),
            ),
            FeatureValue(
                "policy.causal_claim_allowed",
                False,
                (f"outcome:{outcome.id}",),
            ),
        )
        source_fingerprint = hashlib.sha256(
            (
                pre.input_fingerprint
                + "|"
                + post.input_fingerprint
                + "|"
                + str(outcome.id)
                + "|"
                + OUTCOME_FEATURE_SCHEMA_VERSION
            ).encode("utf-8")
        ).hexdigest()
        flags = tuple(
            sorted(set(pre.data_quality_flags).union(post.data_quality_flags))
        )
        now = datetime.now(UTC)
        package = FeaturePackage(
            id=uuid4(),
            household_id=outcome.household_id,
            assessment_id=outcome.post_assessment_id,
            pgor_snapshot_id=post.id,
            package_type=FeaturePackageType.OUTCOME,
            schema_version=OUTCOME_FEATURE_SCHEMA_VERSION,
            source_fingerprint=source_fingerprint,
            data_quality_flags=flags,
            values=values,
            created_at=now,
            created_by=command.actor_id,
        )
        await self._feature_packages.add(package)
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="FeaturePackageBuilt",
                event_version=1,
                aggregate_type="FEATURE_PACKAGE",
                aggregate_id=package.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "feature_package_id": str(package.id),
                    "household_id": str(package.household_id),
                    "outcome_id": str(outcome.id),
                    "package_type": package.package_type.value,
                    "schema_version": package.schema_version,
                    "source_fingerprint": package.source_fingerprint,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="intelligence.feature_package.build",
                resource_type="FEATURE_PACKAGE",
                resource_id=package.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_OUTCOME_INTERPRETATION",
                metadata={
                    "event_id": str(event_id),
                    "outcome_id": str(outcome.id),
                    "post_pgor_snapshot_id": str(post.id),
                    "source_fingerprint": package.source_fingerprint,
                },
            )
        )
        household_context_version = (
            await self._accepted_state.context_version(outcome.household_id)
            if self._accepted_state is not None
            else None
        )
        return PreparedOutcomeInterpretation(
            outcome_id=outcome.id,
            household_id=outcome.household_id,
            intervention_id=outcome.intervention_id,
            referral_id=outcome.referral_id,
            provider_result_id=outcome.provider_result_id,
            post_snapshot=post,
            feature_package=package,
            household_context_version=household_context_version,
        )

    async def infer(
        self,
        *,
        prepared: PreparedOutcomeInterpretation,
        correlation_id: str,
    ) -> AIExecutionResult:
        result = await self._ai_client.generate_outcome_interpretation(
            feature_package=prepared.feature_package,
            correlation_id=correlation_id,
        )
        _validate_output(output=result.output, package=prepared.feature_package)
        return result

    async def persist(
        self,
        *,
        command: GenerateOutcomeInterpretationCommand,
        prepared: PreparedOutcomeInterpretation,
        result: AIExecutionResult,
    ) -> tuple[OutcomeInterpretationProposal, AIDecision]:
        if (
            prepared.household_context_version is not None
            and self._accepted_state is not None
        ):
            current_context_version = await self._accepted_state.context_version(
                prepared.household_id
            )
            if current_context_version != prepared.household_context_version:
                raise OutcomeInterpretationError(
                    "HOUSEHOLD_CONTEXT_VERSION_CONFLICT"
                )
        now = datetime.now(UTC)
        trace_id = uuid4()
        ai_decision = AIDecision(
            id=uuid4(),
            household_id=prepared.household_id,
            assessment_id=prepared.feature_package.assessment_id,
            feature_package_id=prepared.feature_package.id,
            pgor_snapshot_id=prepared.post_snapshot.id,
            decision_type=AIDecisionType.OUTCOME_INTERPRETATION,
            status=AIDecisionStatus.GENERATED,
            provider_code=result.provider_code,
            model_id=result.model_id,
            model_alias=result.model_alias,
            routing_policy_id=result.routing_policy_id,
            routing_policy_version=result.routing_policy_version,
            prompt_policy_version=result.prompt_policy_version,
            output_schema_version=result.output_schema_version,
            structured_output=result.output,
            trace_id=trace_id,
            generated_at=now,
        )
        proposal = OutcomeInterpretationProposal(
            id=uuid4(),
            outcome_id=prepared.outcome_id,
            ai_decision_id=ai_decision.id,
            created_at=now,
        )
        trace = DecisionTrace(
            id=trace_id,
            household_id=prepared.household_id,
            trace_type=AIDecisionType.OUTCOME_INTERPRETATION,
            state_fingerprint=prepared.feature_package.source_fingerprint,
            household_context_version=prepared.household_context_version,
            pgor_snapshot_id=prepared.post_snapshot.id,
            feature_package_id=prepared.feature_package.id,
            ai_decision_id=ai_decision.id,
            opened_at=now,
            intervention_id=prepared.intervention_id,
            referral_id=prepared.referral_id,
            provider_result_id=prepared.provider_result_id,
            outcome_id=prepared.outcome_id,
        )
        await self._ai_decisions.add(ai_decision)
        await self._proposals.add(proposal)
        await self._traces.add(trace)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="OutcomeInterpretationProposed",
                event_version=1,
                aggregate_type="HAMOON_OUTCOME",
                aggregate_id=prepared.outcome_id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "outcome_id": str(prepared.outcome_id),
                    "proposal_id": str(proposal.id),
                    "ai_decision_id": str(ai_decision.id),
                    "feature_package_id": str(prepared.feature_package.id),
                    "trace_id": str(trace.id),
                    "model_alias": ai_decision.model_alias,
                    "routing_policy_version": ai_decision.routing_policy_version,
                    "prompt_policy_version": ai_decision.prompt_policy_version,
                    "output_schema_version": ai_decision.output_schema_version,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="outcome.interpretation.generate",
                resource_type="HAMOON_OUTCOME",
                resource_id=prepared.outcome_id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_OUTCOME_INTERPRETATION",
                metadata={
                    "event_id": str(event_id),
                    "proposal_id": str(proposal.id),
                    "ai_decision_id": str(ai_decision.id),
                    "trace_id": str(trace.id),
                    "feature_package_id": str(prepared.feature_package.id),
                    "model_alias": ai_decision.model_alias,
                },
            )
        )
        return proposal, ai_decision
