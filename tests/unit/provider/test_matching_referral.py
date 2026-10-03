from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.domains.family_data.domain.entities import CurrentAcceptedFact, HouseholdFact, FactValueType
from hamoon.domains.intelligence.domain.decisions import HumanDecision
from hamoon.domains.intervention.domain.entities import Intervention, InterventionStatus, InterventionType
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.provider.application.commands import MatchProvidersCommand
from hamoon.domains.provider.application.matching import MatchProvidersHandler
from hamoon.domains.provider.domain.entities import (
    CapacityStatus,
    EligibilityOperator,
    MatchEligibility,
    Provider,
    ProviderCapacitySnapshot,
    ProviderEligibilityRule,
    ProviderService,
    ProviderStatus,
)
from hamoon.domains.referral.application.commands import CreateReferralCommand, SharedFactInput
from hamoon.domains.referral.application.handlers import CreateReferralHandler

ACTOR=UUID("11111111-1111-1111-1111-111111111111")
HH=UUID("22222222-2222-2222-2222-222222222222")
INT=UUID("33333333-3333-3333-3333-333333333333")
PROVIDER=UUID("44444444-4444-4444-4444-444444444444")
SERVICE=UUID("55555555-5555-5555-5555-555555555555")
FACT=UUID("66666666-6666-6666-6666-666666666666")


class InterventionRepo:
    async def get(self, intervention_id):
        if intervention_id != INT:
            return None
        return Intervention(
            id=INT,
            household_id=HH,
            prescription_item_id=UUID("77777777-7777-7777-7777-777777777777"),
            intervention_type=InterventionType.MARKET_LINKAGE,
            target_pgor_variable=PGORVariableCode.O,
            status=InterventionStatus.ACTIVE,
            started_at=datetime.now(UTC),
            completed_at=None,
            owner_actor_id=ACTOR,
        )


class AcceptedRepo:
    def __init__(self):
        self.item=CurrentAcceptedFact(
            household_id=HH,
            fact_type="geo.coverage_code",
            fact_id=FACT,
            accepted_value="TEHRAN-1",
            source_id=UUID("88888888-8888-8888-8888-888888888888"),
            effective_from=datetime.now(UTC),
            projection_version=3,
            projected_at=datetime.now(UTC),
            changed_by=ACTOR,
        )
    async def list_for_household(self, household_id):
        return [self.item] if household_id == HH else []
    async def get(self, *, household_id, fact_type):
        return self.item if household_id == HH and fact_type == self.item.fact_type else None
    async def set_current(self, **kwargs):
        raise AssertionError("not used")


class Registry:
    async def get_provider(self, provider_id):
        if provider_id != PROVIDER:
            return None
        return Provider(PROVIDER,"p1","Provider 1",ProviderStatus.ACTIVE,None,"API",datetime.now(UTC))
    async def list_providers(self):
        item=await self.get_provider(PROVIDER)
        return [] if item is None else [item]
    async def get_service(self, service_id):
        if service_id != SERVICE:
            return None
        return ProviderService(
            id=SERVICE,
            provider_id=PROVIDER,
            service_type="EMPLOYMENT_MARKET",
            title="Market linkage",
            description="",
            supported_intervention_types=(InterventionType.MARKET_LINKAGE,),
            eligibility_policy_version="elig-v1",
            coverage_policy_version="cov-v1",
            coverage_fact_type="geo.coverage_code",
            coverage_codes=("TEHRAN-1",),
            sla_policy_version=None,
            active=True,
        )
    async def list_services_for_provider(self, provider_id):
        item=await self.get_service(SERVICE)
        return [] if provider_id != PROVIDER or item is None else [item]
    async def list_services_by_type(self, service_type):
        item=await self.get_service(SERVICE)
        return [] if service_type != "EMPLOYMENT_MARKET" or item is None else [item]
    async def list_eligibility_rules(self, provider_service_id):
        if provider_service_id != SERVICE:
            return []
        return [
            ProviderEligibilityRule(
                id=UUID("99999999-9999-9999-9999-999999999999"),
                provider_service_id=SERVICE,
                fact_type="geo.coverage_code",
                operator=EligibilityOperator.EXISTS,
                expected_value=None,
                reason_code="MISSING_COVERAGE_FACT",
                active=True,
            )
        ]
    async def latest_capacity(self, provider_service_id):
        if provider_service_id != SERVICE:
            return None
        return ProviderCapacitySnapshot(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            provider_service_id=SERVICE,
            capacity_status=CapacityStatus.AVAILABLE,
            available_slots=4,
            valid_at=datetime.now(UTC),
            received_at=datetime.now(UTC),
            source_reference=None,
        )


class MatchRepo:
    def __init__(self):
        self.match=None
    async def add(self, match):
        self.match=match
    async def get(self, match_id):
        return self.match if self.match and self.match.id == match_id else None
    async def get_latest_for_intervention(self, intervention_id):
        return self.match if self.match and self.match.intervention_id == intervention_id else None
    async def get_candidate(self, *, provider_match_id, provider_id, provider_service_id):
        if not self.match or self.match.id != provider_match_id:
            return None
        return next((x for x in self.match.candidates if x.provider_id == provider_id and x.provider_service_id == provider_service_id),None)


class Recorder:
    def __init__(self):
        self.items=[]
    async def record(self,item):
        self.items.append(item)


class FactRepo:
    async def get_for_household(self, *, household_id, fact_id):
        if household_id != HH or fact_id != FACT:
            return None
        return HouseholdFact(
            id=FACT,
            household_id=HH,
            fact_type="geo.coverage_code",
            value_type=FactValueType.CODE,
            value="TEHRAN-1",
            source_id=UUID("88888888-8888-8888-8888-888888888888"),
            effective_from=datetime.now(UTC),
            recorded_at=datetime.now(UTC),
            recorded_by=ACTOR,
        )
    async def add(self, fact):
        raise AssertionError("not used")
    async def list_for_household(self, household_id):
        return []


class SelectionRepo:
    def __init__(self): self.item=None
    async def add(self,item): self.item=item


class ReferralRepo:
    def __init__(self): self.item=None
    async def add(self,item): self.item=item
    async def get(self,referral_id): return self.item if self.item and self.item.id == referral_id else None


class HumanRepo:
    def __init__(self): self.items:list[HumanDecision]=[]
    async def add(self,item): self.items.append(item)
    async def get(self,item_id): return next((x for x in self.items if x.id == item_id),None)


class LearningRepo:
    def __init__(self): self.items=[]
    async def add(self,item): self.items.append(item)


@pytest.mark.asyncio
async def test_rule_based_matching_returns_explainable_candidate_without_winner() -> None:
    matches=MatchRepo()
    events=Recorder()
    match=await MatchProvidersHandler(
        interventions=InterventionRepo(),
        accepted_state=AcceptedRepo(),
        registry=Registry(),
        matches=matches,
        events=events,
        audits=Recorder(),
    ).handle(
        MatchProvidersCommand(
            intervention_id=INT,
            service_type="EMPLOYMENT_MARKET",
            household_context_version=3,
            actor_id=ACTOR,
            request_id="req",
            correlation_id="corr",
        )
    )
    assert len(match.candidates) == 1
    assert match.candidates[0].eligibility is MatchEligibility.ELIGIBLE
    assert match.candidates[0].reasons == ()
    assert events.items[0].event_type == "ProviderMatchGenerated"
    assert "winner" not in events.items[0].payload


@pytest.mark.asyncio
async def test_human_selection_creates_ready_referral_and_learning_signal() -> None:
    matches=MatchRepo()
    await MatchProvidersHandler(
        interventions=InterventionRepo(),
        accepted_state=AcceptedRepo(),
        registry=Registry(),
        matches=matches,
        events=Recorder(),
        audits=Recorder(),
    ).handle(
        MatchProvidersCommand(
            intervention_id=INT,
            service_type="EMPLOYMENT_MARKET",
            household_context_version=3,
            actor_id=ACTOR,
            request_id="req",
            correlation_id="corr",
        )
    )
    learning=LearningRepo()
    referral, selection, human, signal=await CreateReferralHandler(
        interventions=InterventionRepo(),
        registry=Registry(),
        matches=matches,
        selections=SelectionRepo(),
        referrals=ReferralRepo(),
        facts=FactRepo(),
        accepted_state=AcceptedRepo(),
        human_decisions=HumanRepo(),
        learning_signals=learning,
        events=Recorder(),
        audits=Recorder(),
    ).handle(
        CreateReferralCommand(
            intervention_id=INT,
            provider_id=PROVIDER,
            provider_service_id=SERVICE,
            priority="NORMAL",
            response_due_at=None,
            shared_data_items=(SharedFactInput(source_fact_id=FACT,purpose="SERVICE_ELIGIBILITY"),),
            actor_id=ACTOR,
            request_id="req2",
            correlation_id="corr2",
        )
    )
    assert referral.status.value == "READY"
    assert referral.data_items[0].shared_at is None
    assert selection.human_decision_id == human.id
    assert human.ai_decision_id is None
    assert signal.signal_type.value == "PROVIDER_SELECTED"
    assert signal.provider_id == PROVIDER
