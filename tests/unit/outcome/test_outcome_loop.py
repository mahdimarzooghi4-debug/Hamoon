from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from hamoon.domains.assessment.domain.entities import (
    Assessment,
    AssessmentStatus,
    AssessmentType,
)
from hamoon.domains.intelligence.domain.decisions import HumanDecision, LearningSignal
from hamoon.domains.intervention.domain.entities import (
    Intervention,
    InterventionStatus,
    InterventionType,
)
from hamoon.domains.outcome.application.commands import (
    PrepareOutcomeCommand,
    ReviewOutcomeCommand,
)
from hamoon.domains.outcome.application.handlers import (
    PrepareOutcomeHandler,
    ReviewOutcomeHandler,
)
from hamoon.domains.outcome.domain.entities import (
    OutcomeClassification,
    OutcomeStatus,
)
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import EBand, PBand, PGORSnapshotStatus, RBand
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.provider_result.domain.entities import ProviderResult
from hamoon.domains.referral.domain.entities import Referral, ReferralStatus
from hamoon.domains.intelligence.domain.decisions import HumanDecisionAction

ACTOR=UUID("11111111-1111-1111-1111-111111111111")
HH=UUID("22222222-2222-2222-2222-222222222222")
INT=UUID("33333333-3333-3333-3333-333333333333")
PRE_A=UUID("44444444-4444-4444-4444-444444444444")
POST_A=UUID("55555555-5555-5555-5555-555555555555")
PRE_S=UUID("66666666-6666-6666-6666-666666666666")
POST_S=UUID("77777777-7777-7777-7777-777777777777")
PR=UUID("88888888-8888-8888-8888-888888888888")
REF=UUID("99999999-9999-9999-9999-999999999999")
PROVIDER=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DEF=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
FORMULA=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


class Interventions:
    async def get(self,item_id):
        if item_id != INT:
            return None
        return Intervention(INT,HH,UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),InterventionType.MARKET_LINKAGE,PGORVariableCode.O,InterventionStatus.ACTIVE,datetime.now(UTC),None,ACTOR)


class Assessments:
    async def add(self,item): pass
    async def get(self,item_id):
        if item_id == PRE_A:
            return Assessment(PRE_A,HH,AssessmentType.BASELINE,DEF,AssessmentStatus.COMPLETED,1,datetime.now(UTC),ACTOR)
        if item_id == POST_A:
            return Assessment(POST_A,HH,AssessmentType.OUTCOME_REASSESSMENT,DEF,AssessmentStatus.COMPLETED,1,datetime.now(UTC),ACTOR,intervention_id=INT,provider_result_id=PR,parent_assessment_id=PRE_A)
        return None


def snapshot(snapshot_id, assessment_id, p,g,o,r,e):
    return PGORSnapshot(snapshot_id,HH,assessment_id,DEF,FORMULA,"1","1",PGORSnapshotStatus.OFFICIAL,Decimal(p),Decimal(g),Decimal(o),Decimal(r),Decimal(e),(PGORVariableCode.O,),EBand.SUPPORTED_EMPOWERMENT,PBand.DESIRABLE,RBand.ACCEPTABLE,Decimal("1"),(),snapshot_id.hex[:64].ljust(64,"0"),datetime.now(UTC),ACTOR)


class Snapshots:
    async def create(self,**kwargs): raise AssertionError
    async def get(self,item_id): return None
    async def list_inputs(self,item_id): return []
    async def get_official_by_assessment(self,assessment_id):
        if assessment_id == PRE_A:
            return snapshot(PRE_S, PRE_A, "0.8", "0.7", "0.2", "0.6", "0.46")
        if assessment_id == POST_A:
            return snapshot(POST_S, POST_A, "0.82", "0.72", "0.35", "0.61", "0.53")
        return None


class Results:
    async def add(self,item): pass
    async def get(self,item_id):
        if item_id != PR:
            return None
        return ProviderResult(PR,REF,PROVIDER,"COMPLETED","SERVICE_COMPLETION","done",None,None,None,datetime.now(UTC),"ext-r",None,"a"*64,())
    async def get_by_external_result(self,**kwargs): return None
    async def list_for_referral(self,item_id): return []


class Referrals:
    async def add(self,item): pass
    async def get(self,item_id):
        if item_id != REF:
            return None
        return Referral(REF,HH,INT,UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),PROVIDER,UUID("12121212-1212-1212-1212-121212121212"),ReferralStatus.COMPLETED,"NORMAL",3,None,datetime.now(UTC),datetime.now(UTC),datetime.now(UTC),None,"ext-ref","subject",ACTOR,datetime.now(UTC),())
    async def get_by_provider_reference(self,**kwargs): return None
    async def update(self,*args,**kwargs): pass
    async def add_event(self,item): pass
    async def list_events(self,item_id): return []
    async def mark_data_items_shared(self,**kwargs): pass


class Outcomes:
    def __init__(self): self.item=None
    async def add(self,item): self.item=item
    async def get(self,item_id): return self.item if self.item and self.item.id == item_id else None
    async def update(self,item,*,expected_version):
        assert self.item.version == expected_version
        self.item=item


class HumanRepo:
    def __init__(self): self.items:list[HumanDecision]=[]
    async def add(self,item): self.items.append(item)
    async def get(self,item_id): return next((x for x in self.items if x.id == item_id),None)


class LearningRepo:
    def __init__(self): self.items:list[LearningSignal]=[]
    async def add(self,item): self.items.append(item)


class Recorder:
    def __init__(self): self.items=[]
    async def record(self,item): self.items.append(item)


@pytest.mark.asyncio
async def test_outcome_deltas_are_observed_not_causal_and_feed_learning() -> None:
    outcomes=Outcomes()
    prepared=await PrepareOutcomeHandler(
        interventions=Interventions(),
        assessments=Assessments(),
        snapshots=Snapshots(),
        provider_results=Results(),
        referrals=Referrals(),
        outcomes=outcomes,
        events=Recorder(),
        audits=Recorder(),
    ).handle(
        PrepareOutcomeCommand(INT,PRE_A,POST_A,PR,ACTOR,"req","corr")
    )
    assert prepared.e_delta == Decimal("0.07")
    assert prepared.o_delta == Decimal("0.15")
    assert prepared.classification is None
    assert "does not by itself establish causality" in prepared.observed_change_summary

    learning=LearningRepo()
    updated,human,signal=await ReviewOutcomeHandler(
        outcomes=outcomes,
        human_decisions=HumanRepo(),
        learning_signals=learning,
        events=Recorder(),
        audits=Recorder(),
    ).handle(
        ReviewOutcomeCommand(
            prepared.id,
            1,
            OutcomeClassification.PROGRESS,
            None,
            None,
            None,
            ACTOR,
            "req2",
            "corr",
        ),
        action=HumanDecisionAction.CONFIRM,
        target_status=OutcomeStatus.CONFIRMED,
    )
    assert updated.classification is OutcomeClassification.PROGRESS
    assert human.decision_context.value == "OUTCOME"
    assert signal.signal_type.value == "OUTCOME_OBSERVED"
    assert signal.provider_result_id == PR
    assert signal.outcome_id == prepared.id
