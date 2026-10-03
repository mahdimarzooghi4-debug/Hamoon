from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from hamoon.domains.intelligence.domain.decisions import (
    LearningSignal,
    LearningSignalQuality,
    LearningSignalType,
)
from hamoon.domains.intervention.domain.entities import (
    Intervention,
    InterventionStatus,
    InterventionType,
)
from hamoon.domains.learning.application.commands import CreateOutcomeDatasetCommand
from hamoon.domains.learning.application.handlers import CreateOutcomeDatasetHandler
from hamoon.domains.learning.domain.entities import DatasetVersionStatus
from hamoon.domains.learning.domain.errors import LearningDatasetError
from hamoon.domains.outcome.domain.entities import (
    HamoonOutcome,
    OutcomeClassification,
    OutcomeStatus,
)
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import EBand, PBand, PGORSnapshotStatus, RBand
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.provider_result.domain.entities import ProviderResult

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HH = UUID("22222222-2222-2222-2222-222222222222")
SIGNAL = UUID("33333333-3333-3333-3333-333333333333")
OUTCOME = UUID("44444444-4444-4444-4444-444444444444")
INTERVENTION = UUID("55555555-5555-5555-5555-555555555555")
PRE = UUID("66666666-6666-6666-6666-666666666666")
POST = UUID("77777777-7777-7777-7777-777777777777")
PROVIDER_RESULT = UUID("88888888-8888-8888-8888-888888888888")
AI_DECISION = UUID("89898989-8989-8989-8989-898989898989")
DEF = UUID("99999999-9999-9999-9999-999999999999")
FORMULA = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _signal() -> LearningSignal:
    return LearningSignal(
        id=SIGNAL,
        household_id=HH,
        signal_type=LearningSignalType.OUTCOME_OBSERVED,
        ai_decision_id=AI_DECISION,
        human_decision_id=ACTOR,
        diagnosis_id=None,
        signal_label="PROGRESS",
        quality_status=LearningSignalQuality.CURATED,
        created_at=datetime.now(UTC),
        created_by=ACTOR,
        intervention_id=INTERVENTION,
        provider_result_id=PROVIDER_RESULT,
        outcome_id=OUTCOME,
    )


def _outcome() -> HamoonOutcome:
    now = datetime.now(UTC)
    return HamoonOutcome(
        id=OUTCOME,
        household_id=HH,
        intervention_id=INTERVENTION,
        referral_id=None,
        provider_result_id=PROVIDER_RESULT,
        pre_assessment_id=ACTOR,
        post_assessment_id=SIGNAL,
        pre_pgor_snapshot_id=PRE,
        post_pgor_snapshot_id=POST,
        status=OutcomeStatus.CONFIRMED,
        classification=OutcomeClassification.PROGRESS,
        observed_change_summary="observed",
        p_delta=Decimal("0.01"),
        g_delta=Decimal("0.02"),
        o_delta=Decimal("0.15"),
        r_delta=Decimal("0.01"),
        e_delta=Decimal("0.07"),
        confidence=None,
        assessed_at=now,
        assessed_by=ACTOR,
        methodology_version="observed-pgor-delta-v1",
        version=2,
        latest_human_decision_id=ACTOR,
        reviewed_at=now,
        reviewed_by=ACTOR,
    )


class Signals:
    def __init__(self, signal: LearningSignal | None = None) -> None:
        self.signal = signal or _signal()

    async def get(self, signal_id):
        return self.signal if signal_id == self.signal.id else None


class Datasets:
    def __init__(self):
        self.dataset = None
        self.items = ()

    async def get_by_key_version(self, **kwargs):
        return None

    async def add(self, dataset, items):
        self.dataset = dataset
        self.items = items

    async def get(self, dataset_id):
        return self.dataset if self.dataset and self.dataset.id == dataset_id else None

    async def list_items(self, dataset_id):
        return list(self.items)

    async def approve(self, dataset):
        self.dataset = dataset


class Outcomes:
    def __init__(self, outcome: HamoonOutcome | None = None) -> None:
        self.outcome = outcome or _outcome()

    async def get(self, outcome_id):
        return self.outcome if outcome_id == self.outcome.id else None


def _snapshot(snapshot_id, e):
    return PGORSnapshot(
        id=snapshot_id,
        household_id=HH,
        assessment_id=ACTOR,
        definition_version_id=DEF,
        formula_version_id=FORMULA,
        engine_version="1",
        scoring_version="1",
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


class Snapshots:
    async def get(self, snapshot_id):
        if snapshot_id == PRE:
            return _snapshot(PRE, "0.46")
        if snapshot_id == POST:
            return _snapshot(POST, "0.53")
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
        if result_id != PROVIDER_RESULT:
            return None
        return ProviderResult(
            id=PROVIDER_RESULT,
            referral_id=ACTOR,
            provider_id=ACTOR,
            result_status="COMPLETED",
            result_type="SERVICE_COMPLETION",
            result_summary="provider free-text",
            result_payload=None,
            service_started_at=None,
            service_completed_at=None,
            submitted_at=datetime.now(UTC),
            external_result_id="external",
            provider_reference=None,
            request_hash="a" * 64,
        )


class Recorder:
    def __init__(self):
        self.items = []

    async def record(self, item):
        self.items.append(item)


async def _create_dataset(
    *,
    signals: Signals | None = None,
    outcomes: Outcomes | None = None,
):
    return await CreateOutcomeDatasetHandler(
        signals=signals or Signals(),
        datasets=Datasets(),
        outcomes=outcomes or Outcomes(),
        snapshots=Snapshots(),
        interventions=Interventions(),
        provider_results=Results(),
        events=Recorder(),
        audits=Recorder(),
    ).handle(
        CreateOutcomeDatasetCommand(
            dataset_key="hamoon.outcome.learning",
            version="v1",
            selection_policy_version="outcome-selection-v1",
            signal_ids=(SIGNAL,),
            actor_id=ACTOR,
            request_id="req",
            correlation_id="corr",
        )
    )


@pytest.mark.asyncio
async def test_curated_outcome_signal_builds_minimized_immutable_dataset() -> None:
    dataset, items = await _create_dataset()

    assert dataset.status is DatasetVersionStatus.DRAFT
    assert len(dataset.manifest_digest) == 64
    assert len(items) == 1
    item = items[0]
    assert item.target_payload["classification"] == "PROGRESS"
    assert item.input_payload["causal_claim_allowed"] is False
    assert "result_summary" not in item.input_payload
    assert f"human_decision:{ACTOR}" in item.source_refs
    assert f"ai_decision:{AI_DECISION}" in item.source_refs
    assert f"provider_result:{PROVIDER_RESULT}" in item.source_refs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("signal", "outcome"),
    [
        (replace(_signal(), household_id=OTHER), _outcome()),
        (replace(_signal(), human_decision_id=OTHER), _outcome()),
        (replace(_signal(), signal_label="REGRESSION"), _outcome()),
        (replace(_signal(), intervention_id=OTHER), _outcome()),
        (replace(_signal(), provider_result_id=OTHER), _outcome()),
    ],
)
async def test_outcome_dataset_rejects_mismatched_signal_provenance(
    signal: LearningSignal,
    outcome: HamoonOutcome,
) -> None:
    with pytest.raises(
        LearningDatasetError,
        match="OUTCOME_SIGNAL_PROVENANCE_MISMATCH",
    ):
        await _create_dataset(
            signals=Signals(signal),
            outcomes=Outcomes(outcome),
        )


@pytest.mark.asyncio
async def test_outcome_dataset_requires_final_human_review_provenance() -> None:
    outcome = replace(
        _outcome(),
        latest_human_decision_id=None,
        reviewed_at=None,
    )

    with pytest.raises(
        LearningDatasetError,
        match="REVIEWED_OUTCOME_REQUIRED",
    ):
        await _create_dataset(outcomes=Outcomes(outcome))
