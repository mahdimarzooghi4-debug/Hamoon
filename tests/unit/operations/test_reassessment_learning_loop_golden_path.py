from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from hamoon.domains.assessment.domain.entities import (
    Assessment,
    AssessmentStatus,
    AssessmentType,
)
from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionType,
    DecisionTrace,
    HumanDecision,
    HumanDecisionAction,
    LearningSignal,
    LearningSignalQuality,
)
from hamoon.domains.intervention.domain.entities import (
    Intervention,
    InterventionStatus,
    InterventionType,
)
from hamoon.domains.learning.application.commands import (
    CreateOutcomeDatasetCommand,
    CurateLearningSignalCommand,
)
from hamoon.domains.learning.application.handlers import (
    CreateOutcomeDatasetHandler,
    CurateLearningSignalHandler,
)
from hamoon.domains.operations.application.handlers import (
    CreateOutcomeReviewWorkItemHandler,
    FinalizeOutcomeReviewHandler,
    MarkPostPGORReadyHandler,
    MaterializeReassessmentWorkItemHandler,
    StartPlannedReassessmentHandler,
)
from hamoon.domains.operations.domain.entities import (
    ReassessmentPlanStatus,
    WorkItemStatus,
    WorkItemType,
)
from hamoon.domains.outcome.application.commands import (
    PrepareOutcomeCommand,
    ReviewOutcomeCommand,
)
from hamoon.domains.outcome.application.handlers import (
    PrepareOutcomeHandler,
    ReviewOutcomeHandler,
)
from hamoon.domains.outcome.application.intelligence import (
    GenerateOutcomeInterpretationCommand,
    GenerateOutcomeInterpretationHandler,
)
from hamoon.domains.outcome.domain.entities import (
    HamoonOutcome,
    OutcomeClassification,
    OutcomeStatus,
)
from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionStatus,
    PGORDefinitionVersion,
    PGORVariableCode,
    RequirementPolicyStatus,
)
from hamoon.domains.pgor.domain.engine import EBand, PBand, PGORSnapshotStatus, RBand
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.prescription.domain.entities import (
    Prescription,
    PrescriptionItem,
    PrescriptionItemStatus,
    PrescriptionStatus,
)
from hamoon.domains.provider_result.application.commands import SubmitProviderResultCommand
from hamoon.domains.provider_result.application.handlers import SubmitProviderResultHandler
from hamoon.domains.referral.domain.entities import Referral, ReferralStatus
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.outcome_runtime import (
    GatewayOutcomeAIClient,
    local_fake_outcome_policy,
)
from hamoon.infrastructure.ai.providers.fake import FakeAIProvider

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD = UUID("22222222-2222-2222-2222-222222222222")
INTERVENTION_ID = UUID("33333333-3333-3333-3333-333333333333")
PRESCRIPTION_ID = UUID("44444444-4444-4444-4444-444444444444")
PRESCRIPTION_ITEM_ID = UUID("55555555-5555-5555-5555-555555555555")
REFERRAL_ID = UUID("66666666-6666-6666-6666-666666666666")
PROVIDER = UUID("77777777-7777-7777-7777-777777777777")
PRE_ASSESSMENT_ID = UUID("88888888-8888-8888-8888-888888888888")
PRE_SNAPSHOT_ID = UUID("99999999-9999-9999-9999-999999999999")
POST_SNAPSHOT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DEFINITION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
FORMULA_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
DIAGNOSIS_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
PRESCRIPTION_AI_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


class Recorder:
    def __init__(self) -> None:
        self.items = []

    async def record(self, item) -> None:
        self.items.append(item)


class Plans:
    def __init__(self) -> None:
        self.item = None

    async def add(self, plan) -> None:
        self.item = plan

    async def get(self, plan_id):
        if self.item is not None and self.item.id == plan_id:
            return self.item
        return None

    async def get_by_provider_result(self, provider_result_id):
        if self.item is not None and self.item.provider_result_id == provider_result_id:
            return self.item
        return None

    async def get_by_outcome(self, outcome_id):
        if self.item is not None and self.item.outcome_id == outcome_id:
            return self.item
        return None

    async def update(self, plan, *, expected_version) -> None:
        assert self.item is not None
        assert self.item.version == expected_version
        self.item = plan


class WorkItems:
    def __init__(self) -> None:
        self.items = {}

    async def add(self, item) -> None:
        self.items[item.id] = item

    async def get(self, item_id):
        return self.items.get(item_id)

    async def update(self, item, *, expected_version) -> None:
        current = self.items[item.id]
        assert current.version == expected_version
        self.items[item.id] = item


class Assessments:
    def __init__(self, pre: Assessment) -> None:
        self.items = {pre.id: pre}

    async def add(self, item) -> None:
        self.items[item.id] = item

    async def get(self, item_id):
        return self.items.get(item_id)


class Definitions:
    async def get_version(self, definition_version_id):
        if definition_version_id != DEFINITION_ID:
            return None
        return PGORDefinitionVersion(
            id=DEFINITION_ID,
            code="PGOR",
            version="v1",
            status=PGORDefinitionStatus.ACTIVE,
            requirement_policy_status=RequirementPolicyStatus.RESOLVED,
            source_reference="golden-path",
        )


class Interventions:
    def __init__(self, intervention: Intervention) -> None:
        self.item = intervention

    async def get(self, intervention_id):
        return self.item if intervention_id == self.item.id else None


class Prescriptions:
    def __init__(self, prescription: Prescription, item: PrescriptionItem) -> None:
        self.prescription = prescription
        self.item = item

    async def get(self, prescription_id):
        return self.prescription if prescription_id == self.prescription.id else None

    async def get_item_by_id(self, item_id):
        return self.item if item_id == self.item.id else None


class Results:
    def __init__(self) -> None:
        self.items = {}

    async def add(self, item) -> None:
        self.items[item.id] = item

    async def get(self, item_id):
        return self.items.get(item_id)

    async def get_by_external_result(self, *, provider_id, external_result_id):
        for item in self.items.values():
            if (
                item.provider_id == provider_id
                and item.external_result_id == external_result_id
            ):
                return item
        return None

    async def list_for_referral(self, referral_id):
        return [item for item in self.items.values() if item.referral_id == referral_id]


class Referrals:
    def __init__(self, referral: Referral) -> None:
        self.item = referral

    async def get(self, referral_id):
        return self.item if referral_id == self.item.id else None

    async def get_by_provider_reference(
        self,
        *,
        provider_id,
        external_referral_id,
    ):
        if (
            provider_id == self.item.provider_id
            and external_referral_id == self.item.external_referral_id
        ):
            return self.item
        return None


class Snapshots:
    def __init__(self, pre: PGORSnapshot) -> None:
        self.items = {pre.id: pre}

    def add(self, snapshot: PGORSnapshot) -> None:
        self.items[snapshot.id] = snapshot

    async def get(self, snapshot_id):
        return self.items.get(snapshot_id)

    async def get_official_by_assessment(self, assessment_id):
        return next(
            (
                item
                for item in self.items.values()
                if item.assessment_id == assessment_id
                and item.status is PGORSnapshotStatus.OFFICIAL
            ),
            None,
        )


class Outcomes:
    def __init__(self) -> None:
        self.item: HamoonOutcome | None = None

    async def add(self, item) -> None:
        self.item = item

    async def get(self, outcome_id):
        if self.item is not None and self.item.id == outcome_id:
            return self.item
        return None

    async def get_by_post_assessment(self, post_assessment_id):
        if self.item is not None and self.item.post_assessment_id == post_assessment_id:
            return self.item
        return None

    async def update(self, item, *, expected_version) -> None:
        assert self.item is not None
        assert self.item.version == expected_version
        self.item = item


class Packages:
    def __init__(self) -> None:
        self.item = None

    async def add(self, item) -> None:
        self.item = item

    async def get(self, package_id):
        if self.item is not None and self.item.id == package_id:
            return self.item
        return None

    async def get_by_snapshot(self, *, snapshot_id, schema_version):
        if (
            self.item is not None
            and self.item.pgor_snapshot_id == snapshot_id
            and self.item.schema_version == schema_version
        ):
            return self.item
        return None


class Decisions:
    def __init__(self) -> None:
        self.items: dict[UUID, AIDecision] = {}

    async def add(self, item: AIDecision) -> None:
        self.items[item.id] = item

    async def get(self, item_id):
        return self.items.get(item_id)


class Proposals:
    def __init__(self) -> None:
        self.item = None

    async def add(self, item) -> None:
        self.item = item

    async def get(self, proposal_id):
        if self.item is not None and self.item.id == proposal_id:
            return self.item
        return None

    async def get_by_outcome(self, outcome_id):
        if self.item is not None and self.item.outcome_id == outcome_id:
            return self.item
        return None


class Traces:
    def __init__(self) -> None:
        self.items: dict[UUID, DecisionTrace] = {}

    async def add(self, item: DecisionTrace) -> None:
        self.items[item.ai_decision_id] = item

    async def get_by_ai_decision(self, ai_decision_id):
        return self.items.get(ai_decision_id)

    async def attach_human_decision(
        self,
        *,
        ai_decision_id,
        human_decision_id,
        learning_signal_id=None,
        closed_at=None,
    ) -> None:
        current = self.items[ai_decision_id]
        self.items[ai_decision_id] = replace(
            current,
            human_decision_id=human_decision_id,
            learning_signal_id=learning_signal_id,
            closed_at=closed_at,
        )

    async def attach_referral(self, *, intervention_id, referral_id) -> None:
        current = next(
            item
            for item in self.items.values()
            if item.intervention_id == intervention_id
        )
        self.items[current.ai_decision_id] = replace(
            current,
            referral_id=referral_id,
        )

    async def attach_provider_result(
        self,
        *,
        referral_id,
        provider_result_id,
    ) -> None:
        current = next(
            item
            for item in self.items.values()
            if item.referral_id == referral_id
        )
        self.items[current.ai_decision_id] = replace(
            current,
            provider_result_id=provider_result_id,
        )

    async def attach_outcome(self, *, intervention_id, outcome_id) -> None:
        current = next(
            item
            for item in self.items.values()
            if item.intervention_id == intervention_id
            and item.trace_type is AIDecisionType.PRESCRIPTION
        )
        self.items[current.ai_decision_id] = replace(
            current,
            outcome_id=outcome_id,
        )


class HumanDecisions:
    def __init__(self) -> None:
        self.items: list[HumanDecision] = []

    async def add(self, item: HumanDecision) -> None:
        self.items.append(item)

    async def get(self, item_id):
        return next((item for item in self.items if item.id == item_id), None)


class LearningSignals:
    def __init__(self) -> None:
        self.items: list[LearningSignal] = []

    async def add(self, item: LearningSignal) -> None:
        self.items.append(item)

    async def get(self, signal_id):
        return next((item for item in self.items if item.id == signal_id), None)

    async def change_quality(
        self,
        *,
        signal_id,
        expected_quality,
        new_quality,
    ):
        for index, item in enumerate(self.items):
            if item.id != signal_id:
                continue
            assert item.quality_status is expected_quality
            updated = replace(item, quality_status=new_quality)
            self.items[index] = updated
            return updated
        raise AssertionError("learning signal not found")


class LearningDatasets:
    def __init__(self) -> None:
        self.dataset = None
        self.items = ()

    async def get_by_key_version(self, **_kwargs):
        return None

    async def add(self, dataset, items) -> None:
        self.dataset = dataset
        self.items = items

    async def get(self, dataset_id):
        if self.dataset is not None and self.dataset.id == dataset_id:
            return self.dataset
        return None

    async def list_items(self, dataset_id):
        if self.dataset is None or self.dataset.id != dataset_id:
            return []
        return list(self.items)

    async def approve(self, dataset) -> None:
        self.dataset = dataset


def _snapshot(
    *,
    snapshot_id: UUID,
    assessment_id: UUID,
    p: str,
    g: str,
    o: str,
    r: str,
    e: str,
) -> PGORSnapshot:
    return PGORSnapshot(
        id=snapshot_id,
        household_id=HOUSEHOLD,
        assessment_id=assessment_id,
        definition_version_id=DEFINITION_ID,
        formula_version_id=FORMULA_ID,
        engine_version="engine-v1",
        scoring_version="score-v1",
        status=PGORSnapshotStatus.OFFICIAL,
        p=Decimal(p),
        g=Decimal(g),
        o=Decimal(o),
        r=Decimal(r),
        e=Decimal(e),
        bottleneck_variables=(PGORVariableCode.O,),
        e_band=EBand.SUPPORTED_EMPOWERMENT,
        p_band=PBand.DESIRABLE,
        r_band=RBand.ACCEPTABLE,
        completeness_ratio=Decimal("1"),
        data_quality_flags=(),
        input_fingerprint=snapshot_id.hex[:64].ljust(64, "0"),
        calculated_at=datetime.now(UTC),
        calculated_by=ACTOR,
    )


@pytest.mark.asyncio
async def test_reassessment_learning_loop_golden_path() -> None:
    events = Recorder()
    audits = Recorder()
    plans = Plans()
    work_items = WorkItems()
    results = Results()
    traces = Traces()

    pre_assessment = Assessment(
        id=PRE_ASSESSMENT_ID,
        household_id=HOUSEHOLD,
        assessment_type=AssessmentType.BASELINE,
        definition_version_id=DEFINITION_ID,
        status=AssessmentStatus.COMPLETED,
        version=1,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        started_by=ACTOR,
    )
    assessments = Assessments(pre_assessment)
    pre_snapshot = _snapshot(
        snapshot_id=PRE_SNAPSHOT_ID,
        assessment_id=PRE_ASSESSMENT_ID,
        p="0.80",
        g="0.70",
        o="0.20",
        r="0.60",
        e="0.46",
    )
    snapshots = Snapshots(pre_snapshot)

    prescription = Prescription(
        id=PRESCRIPTION_ID,
        household_id=HOUSEHOLD,
        diagnosis_id=DIAGNOSIS_ID,
        ai_decision_id=PRESCRIPTION_AI_ID,
        pgor_snapshot_id=PRE_SNAPSHOT_ID,
        status=PrescriptionStatus.APPROVED,
        version=2,
        accepted_payload={"source": "human-reviewed"},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        created_by=ACTOR,
        latest_human_decision_id=ACTOR,
        accepted_at=datetime(2026, 1, 2, tzinfo=UTC),
        accepted_by=ACTOR,
    )
    prescription_item = PrescriptionItem(
        id=PRESCRIPTION_ITEM_ID,
        prescription_id=PRESCRIPTION_ID,
        source_code="PGOR_O_MARKET_LINKAGE",
        intervention_type=InterventionType.MARKET_LINKAGE,
        target_pgor_variable=PGORVariableCode.O,
        priority=1,
        current_value=Decimal("0.20"),
        target_value=Decimal("0.35"),
        success_criteria=("Reassess O after intervention.",),
        review_after_days=30,
        review_rationale="Measure observed change.",
        rationale="Targets the accepted O bottleneck.",
        title="Market linkage",
        status=PrescriptionItemStatus.ACTIVATED,
        machine_proposed=True,
    )
    prescriptions = Prescriptions(prescription, prescription_item)
    intervention = Intervention(
        id=INTERVENTION_ID,
        household_id=HOUSEHOLD,
        prescription_item_id=PRESCRIPTION_ITEM_ID,
        intervention_type=InterventionType.MARKET_LINKAGE,
        target_pgor_variable=PGORVariableCode.O,
        status=InterventionStatus.ACTIVE,
        started_at=datetime(2026, 1, 3, tzinfo=UTC),
        completed_at=None,
        owner_actor_id=ACTOR,
    )
    interventions = Interventions(intervention)
    referral = Referral(
        id=REFERRAL_ID,
        household_id=HOUSEHOLD,
        intervention_id=INTERVENTION_ID,
        provider_match_id=DIAGNOSIS_ID,
        provider_selection_id=PRESCRIPTION_AI_ID,
        provider_id=PROVIDER,
        provider_service_id=FORMULA_ID,
        status=ReferralStatus.COMPLETED,
        priority="NORMAL",
        version=4,
        response_due_at=None,
        sent_at=datetime(2026, 1, 4, tzinfo=UTC),
        accepted_at=datetime(2026, 1, 5, tzinfo=UTC),
        completed_at=datetime(2026, 1, 10, tzinfo=UTC),
        cancelled_at=None,
        external_referral_id="ext-ref-1",
        subject_reference="hh-subject",
        created_by=ACTOR,
        created_at=datetime(2026, 1, 4, tzinfo=UTC),
        data_items=(),
    )
    referrals = Referrals(referral)
    await traces.add(
        DecisionTrace(
            id=DIAGNOSIS_ID,
            household_id=HOUSEHOLD,
            trace_type=AIDecisionType.PRESCRIPTION,
            state_fingerprint="a" * 64,
            pgor_snapshot_id=PRE_SNAPSHOT_ID,
            feature_package_id=FORMULA_ID,
            ai_decision_id=PRESCRIPTION_AI_ID,
            opened_at=datetime(2026, 1, 2, tzinfo=UTC),
            human_decision_id=ACTOR,
            prescription_id=PRESCRIPTION_ID,
            intervention_id=INTERVENTION_ID,
            referral_id=REFERRAL_ID,
        )
    )
    service_completed_at = datetime(2026, 2, 1, tzinfo=UTC)

    submitted = await SubmitProviderResultHandler(
        referrals=referrals,
        results=results,
        events=events,
        audits=audits,
        interventions=interventions,
        prescriptions=prescriptions,
        reassessment_plans=plans,
        traces=traces,
    ).handle(
        SubmitProviderResultCommand(
            provider_id=PROVIDER,
            actor_id=ACTOR,
            external_referral_id="ext-ref-1",
            external_result_id="provider-result-1",
            result_status="COMPLETED",
            result_type="SERVICE_COMPLETION",
            result_summary="Provider free-text must not enter the Outcome AI package.",
            result_payload={"provider_metric": "completed"},
            service_started_at=datetime(2026, 1, 20, tzinfo=UTC),
            service_completed_at=service_completed_at,
            evidence_ids=(),
            provider_reference="provider-case-1",
            correlation_id="golden-loop",
        )
    )
    provider_result = submitted.result
    plan = submitted.reassessment_plan
    assert plan is not None
    assert provider_result.id != plan.id
    assert traces.items[PRESCRIPTION_AI_ID].provider_result_id == provider_result.id
    assert plan.status is ReassessmentPlanStatus.SCHEDULED
    assert plan.due_at == service_completed_at + timedelta(days=30)

    reassessment_item = await MaterializeReassessmentWorkItemHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        plan_id=plan.id,
        actor_id=ACTOR,
        request_id="temporal-materialize",
        correlation_id=plan.workflow_id,
    )

    post_assessment, claimed_item, started_plan = await StartPlannedReassessmentHandler(
        plans=plans,
        work_items=work_items,
        assessments=assessments,
        definitions=Definitions(),
        interventions=interventions,
        provider_results=results,
        referrals=referrals,
        prescriptions=prescriptions,
        snapshots=snapshots,
        events=events,
        audits=audits,
    ).handle(
        work_item_id=reassessment_item.id,
        expected_version=reassessment_item.version,
        actor_id=ACTOR,
        request_id="caseworker-start",
        correlation_id="golden-loop",
    )
    assert post_assessment.assessment_type is AssessmentType.OUTCOME_REASSESSMENT
    assert post_assessment.definition_version_id == pre_assessment.definition_version_id
    assert post_assessment.parent_assessment_id == pre_assessment.id
    assert post_assessment.provider_result_id == provider_result.id
    assert claimed_item.status is WorkItemStatus.CLAIMED
    assert started_plan.status is ReassessmentPlanStatus.REASSESSMENT_STARTED

    # Accepted observations are the authoritative input to deterministic PGOR.
    # The official snapshot below represents that completed deterministic phase;
    # no LLM participates in producing or changing its values.
    assessments.items[post_assessment.id] = replace(
        post_assessment,
        status=AssessmentStatus.COMPLETED,
        version=post_assessment.version + 1,
    )
    post_snapshot = _snapshot(
        snapshot_id=POST_SNAPSHOT_ID,
        assessment_id=post_assessment.id,
        p="0.82",
        g="0.72",
        o="0.35",
        r="0.61",
        e="0.53",
    )
    snapshots.add(post_snapshot)

    ready_plan = await MarkPostPGORReadyHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        provider_result_id=provider_result.id,
        assessment_id=post_assessment.id,
        snapshot_id=post_snapshot.id,
        actor_id=ACTOR,
        request_id="official-pgor",
        correlation_id="golden-loop",
    )
    assert ready_plan.status is ReassessmentPlanStatus.POST_PGOR_READY
    assert work_items.items[reassessment_item.id].status is WorkItemStatus.COMPLETED

    outcomes = Outcomes()
    outcome = await PrepareOutcomeHandler(
        interventions=interventions,
        assessments=assessments,
        snapshots=snapshots,
        provider_results=results,
        referrals=referrals,
        outcomes=outcomes,
        events=events,
        traces=traces,
        audits=audits,
    ).handle(
        PrepareOutcomeCommand(
            intervention_id=INTERVENTION_ID,
            pre_assessment_id=PRE_ASSESSMENT_ID,
            post_assessment_id=post_assessment.id,
            provider_result_id=provider_result.id,
            actor_id=ACTOR,
            request_id="prepare-outcome",
            correlation_id="golden-loop",
        )
    )
    assert outcome.provider_result_id == provider_result.id
    assert outcome.id != provider_result.id
    assert traces.items[PRESCRIPTION_AI_ID].outcome_id == outcome.id
    assert outcome.e_delta == Decimal("0.07")
    assert "does not by itself establish causality" in outcome.observed_change_summary

    packages = Packages()
    decisions = Decisions()
    proposals = Proposals()
    ai_handler = GenerateOutcomeInterpretationHandler(
        outcomes=outcomes,
        proposals=proposals,
        snapshots=snapshots,
        interventions=interventions,
        provider_results=results,
        feature_packages=packages,
        ai_decisions=decisions,
        traces=traces,
        ai_client=GatewayOutcomeAIClient(
            gateway=ProviderAIGateway(providers={"FAKE": FakeAIProvider()}),
            routing_policy=local_fake_outcome_policy(),
        ),
        events=events,
        audits=audits,
    )
    ai_command = GenerateOutcomeInterpretationCommand(
        outcome_id=outcome.id,
        actor_id=ACTOR,
        request_id="outcome-ai",
        correlation_id="golden-loop",
    )
    prepared = await ai_handler.prepare(ai_command)
    feature_payload = prepared.feature_package.provider_payload()
    assert "provider_result.summary" not in feature_payload
    assert "Provider free-text" not in str(feature_payload)
    assert feature_payload["policy.causal_claim_allowed"] is False

    ai_result = await ai_handler.infer(
        prepared=prepared,
        correlation_id="golden-loop",
    )
    proposal, ai_decision = await ai_handler.persist(
        command=ai_command,
        prepared=prepared,
        result=ai_result,
    )
    assert proposal.ai_decision_id == ai_decision.id
    assert ai_decision.structured_output["causal_claim"] is False

    outcome_review_item = await CreateOutcomeReviewWorkItemHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        plan_id=plan.id,
        outcome_id=outcome.id,
        actor_id=ACTOR,
        request_id="outcome-review-item",
        correlation_id=plan.workflow_id,
    )
    assert outcome_review_item.work_type is WorkItemType.OUTCOME_REVIEW
    assert plans.item.status is ReassessmentPlanStatus.OUTCOME_REVIEW

    humans = HumanDecisions()
    learning = LearningSignals()
    reviewed_outcome, human, learning_signal = await ReviewOutcomeHandler(
        outcomes=outcomes,
        human_decisions=humans,
        learning_signals=learning,
        proposals=proposals,
        ai_decisions=decisions,
        traces=traces,
        events=events,
        audits=audits,
    ).handle(
        ReviewOutcomeCommand(
            outcome_id=outcome.id,
            expected_version=outcome.version,
            classification=OutcomeClassification.NO_SIGNIFICANT_CHANGE,
            observed_change_summary=None,
            reason_code=None,
            reason_text=None,
            actor_id=ACTOR,
            request_id="human-review",
            correlation_id="golden-loop",
        ),
        action=HumanDecisionAction.CONFIRM,
        target_status=OutcomeStatus.CONFIRMED,
    )
    assert reviewed_outcome.latest_human_decision_id == human.id
    assert human.ai_decision_id == ai_decision.id
    assert human.accepted_payload is not None
    assert human.accepted_payload["causal_claim"] is False
    assert learning_signal.ai_decision_id == ai_decision.id
    assert learning_signal.human_decision_id == human.id
    assert learning_signal.provider_result_id == provider_result.id
    assert learning_signal.outcome_id == outcome.id

    trace = await traces.get_by_ai_decision(ai_decision.id)
    assert trace is not None
    assert trace.human_decision_id == human.id
    assert trace.closed_at is not None
    assert trace.provider_result_id == provider_result.id
    assert trace.outcome_id == outcome.id

    completed_plan = await FinalizeOutcomeReviewHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        outcome_id=outcome.id,
        actor_id=ACTOR,
        request_id="finalize-loop",
        correlation_id="golden-loop",
    )
    assert completed_plan is not None
    assert completed_plan.status is ReassessmentPlanStatus.COMPLETED
    assert work_items.items[reassessment_item.id].status is WorkItemStatus.COMPLETED
    assert work_items.items[outcome_review_item.id].status is WorkItemStatus.COMPLETED

    curated_signal = await CurateLearningSignalHandler(
        signals=learning,
        events=events,
        audits=audits,
    ).handle(
        CurateLearningSignalCommand(
            signal_id=learning_signal.id,
            expected_quality_status=LearningSignalQuality.RAW,
            to_quality_status=LearningSignalQuality.CURATED,
            reason_code="HUMAN_OUTCOME_REVIEW_VERIFIED",
            actor_id=ACTOR,
            request_id="curate-learning-signal",
            correlation_id="golden-loop",
        )
    )
    assert curated_signal.quality_status is LearningSignalQuality.CURATED

    datasets = LearningDatasets()
    dataset, dataset_items = await CreateOutcomeDatasetHandler(
        signals=learning,
        datasets=datasets,
        outcomes=outcomes,
        snapshots=snapshots,
        interventions=interventions,
        provider_results=results,
        events=events,
        audits=audits,
    ).handle(
        CreateOutcomeDatasetCommand(
            dataset_key="hamoon.outcome.learning",
            version="golden-v1",
            selection_policy_version="outcome-selection-v1",
            signal_ids=(curated_signal.id,),
            actor_id=ACTOR,
            request_id="build-learning-dataset",
            correlation_id="golden-loop",
        )
    )
    assert len(dataset.manifest_digest) == 64
    assert len(dataset_items) == 1
    dataset_item = dataset_items[0]
    assert dataset_item.learning_signal_id == learning_signal.id
    assert dataset_item.target_payload["classification"] == "NO_SIGNIFICANT_CHANGE"
    assert dataset_item.input_payload["causal_claim_allowed"] is False
    assert "Provider free-text" not in str(dataset_item.input_payload)
    assert f"human_decision:{human.id}" in dataset_item.source_refs
    assert f"ai_decision:{ai_decision.id}" in dataset_item.source_refs
    assert f"provider_result:{provider_result.id}" in dataset_item.source_refs

    event_types = [item.event_type for item in events.items]
    for expected in (
        "ProviderResultReceived",
        "ReassessmentScheduled",
        "ReassessmentWorkItemCreated",
        "ReassessmentStarted",
        "ReassessmentPostPGORReady",
        "OutcomePrepared",
        "FeaturePackageBuilt",
        "OutcomeInterpretationProposed",
        "OutcomeReviewWorkItemCreated",
        "OutcomeConfirmed",
        "LearningSignalCreated",
        "ReassessmentLoopCompleted",
        "LearningSignalQualityChanged",
        "DatasetVersionCreated",
    ):
        assert expected in event_types
