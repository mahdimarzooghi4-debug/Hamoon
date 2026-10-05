from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from hamoon.domains.intelligence.domain.decisions import AIDecisionType
from hamoon.domains.intelligence.domain.entities import FeaturePackageType
from hamoon.domains.intervention.domain.entities import (
    Intervention,
    InterventionStatus,
    InterventionType,
)
from hamoon.domains.outcome.application.intelligence import (
    GenerateOutcomeInterpretationCommand,
    GenerateOutcomeInterpretationHandler,
)
from hamoon.domains.outcome.domain.entities import HamoonOutcome, OutcomeStatus
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import EBand, PBand, PGORSnapshotStatus, RBand
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.provider_result.domain.entities import ProviderResult
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.outcome_runtime import (
    GatewayOutcomeAIClient,
    local_fake_outcome_policy,
)
from hamoon.infrastructure.ai.providers.fake import FakeAIProvider

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HH = UUID("22222222-2222-2222-2222-222222222222")
OUTCOME = UUID("33333333-3333-3333-3333-333333333333")
INTERVENTION = UUID("44444444-4444-4444-4444-444444444444")
PRE = UUID("55555555-5555-5555-5555-555555555555")
POST = UUID("66666666-6666-6666-6666-666666666666")
RESULT = UUID("77777777-7777-7777-7777-777777777777")
DEF = UUID("88888888-8888-8888-8888-888888888888")
FORMULA = UUID("99999999-9999-9999-9999-999999999999")


def _snapshot(snapshot_id: UUID, assessment_id: UUID, e: str) -> PGORSnapshot:
    return PGORSnapshot(
        id=snapshot_id,
        household_id=HH,
        assessment_id=assessment_id,
        definition_version_id=DEF,
        formula_version_id=FORMULA,
        engine_version="engine-v1",
        scoring_version="score-v1",
        status=PGORSnapshotStatus.OFFICIAL,
        p=Decimal("0.8"),
        g=Decimal("0.7"),
        o=Decimal("0.3"),
        r=Decimal("0.6"),
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


class Outcomes:
    async def get(self, outcome_id):
        if outcome_id != OUTCOME:
            return None
        return HamoonOutcome(
            id=OUTCOME,
            household_id=HH,
            intervention_id=INTERVENTION,
            referral_id=ACTOR,
            provider_result_id=RESULT,
            pre_assessment_id=ACTOR,
            post_assessment_id=RESULT,
            pre_pgor_snapshot_id=PRE,
            post_pgor_snapshot_id=POST,
            status=OutcomeStatus.UNDER_REVIEW,
            classification=None,
            observed_change_summary="observed",
            p_delta=Decimal("0.01"),
            g_delta=Decimal("0.02"),
            o_delta=Decimal("0.15"),
            r_delta=Decimal("0.01"),
            e_delta=Decimal("0.07"),
            confidence=None,
            assessed_at=datetime.now(UTC),
            assessed_by=ACTOR,
            methodology_version="observed-pgor-delta-v1",
            version=1,
        )


class Proposals:
    def __init__(self):
        self.item = None

    async def get_by_outcome(self, outcome_id):
        return self.item if self.item and self.item.outcome_id == outcome_id else None

    async def add(self, proposal):
        self.item = proposal

    async def get(self, proposal_id):
        return self.item if self.item and self.item.id == proposal_id else None


class Snapshots:
    async def get(self, snapshot_id):
        if snapshot_id == PRE:
            return _snapshot(PRE, ACTOR, "0.46")
        if snapshot_id == POST:
            return _snapshot(POST, RESULT, "0.53")
        return None


class Interventions:
    async def get(self, intervention_id):
        if intervention_id != INTERVENTION:
            return None
        return Intervention(
            id=INTERVENTION,
            household_id=HH,
            prescription_item_id=ACTOR,
            intervention_type=InterventionType.MARKET_LINKAGE,
            target_pgor_variable=PGORVariableCode.O,
            status=InterventionStatus.ACTIVE,
            started_at=datetime.now(UTC),
            completed_at=None,
            owner_actor_id=ACTOR,
        )


class Results:
    async def get(self, result_id):
        if result_id != RESULT:
            return None
        return ProviderResult(
            id=RESULT,
            referral_id=ACTOR,
            provider_id=ACTOR,
            result_status="COMPLETED",
            result_type="SERVICE_COMPLETION",
            result_summary="not sent to model",
            result_payload=None,
            service_started_at=None,
            service_completed_at=None,
            submitted_at=datetime.now(UTC),
            external_result_id="external",
            provider_reference=None,
            request_hash="a" * 64,
        )


class Packages:
    def __init__(self):
        self.item = None

    async def get_by_snapshot(self, *, snapshot_id, schema_version):
        return self.item

    async def add(self, package):
        self.item = package

    async def get(self, package_id):
        return self.item if self.item and self.item.id == package_id else None


class Store:
    def __init__(self):
        self.items = []

    async def add(self, item):
        self.items.append(item)


class AcceptedStateRepo:
    def __init__(self, version: int = 13) -> None:
        self.version = version

    async def context_version(self, household_id: UUID) -> int:
        assert household_id == HH
        return self.version


class Recorder:
    def __init__(self):
        self.items = []

    async def record(self, item):
        self.items.append(item)


@pytest.mark.asyncio
async def test_outcome_ai_builds_minimized_feature_package_and_trace() -> None:
    packages = Packages()
    decisions = Store()
    traces = Store()
    proposals = Proposals()
    accepted_state = AcceptedStateRepo()
    handler = GenerateOutcomeInterpretationHandler(
        outcomes=Outcomes(),
        proposals=proposals,
        snapshots=Snapshots(),
        interventions=Interventions(),
        provider_results=Results(),
        feature_packages=packages,
        ai_decisions=decisions,
        traces=traces,
        accepted_state=accepted_state,
        ai_client=GatewayOutcomeAIClient(
            gateway=ProviderAIGateway(providers={"FAKE": FakeAIProvider()}),
            routing_policy=local_fake_outcome_policy(),
        ),
        events=Recorder(),
        audits=Recorder(),
    )
    command = GenerateOutcomeInterpretationCommand(
        outcome_id=OUTCOME,
        actor_id=ACTOR,
        request_id="req",
        correlation_id="corr",
    )
    prepared = await handler.prepare(command)
    payload = prepared.feature_package.provider_payload()
    assert prepared.feature_package.package_type is FeaturePackageType.OUTCOME
    assert payload["pgor.delta.E"] == "0.07"
    assert payload["policy.causal_claim_allowed"] is False
    assert "provider_result.summary" not in payload

    result = await handler.infer(prepared=prepared, correlation_id="corr")
    proposal, ai_decision = await handler.persist(
        command=command,
        prepared=prepared,
        result=result,
    )
    assert ai_decision.decision_type is AIDecisionType.OUTCOME_INTERPRETATION
    assert ai_decision.structured_output["causal_claim"] is False
    assert proposal.ai_decision_id == ai_decision.id
    assert traces.items[0].outcome_id == OUTCOME
    assert traces.items[0].provider_result_id == RESULT
    assert traces.items[0].household_context_version == 13
