from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from hamoon.domains.operations.domain.entities import (
    ReassessmentPlan,
    ReassessmentPlanStatus,
)
from hamoon.domains.provider_result.api import routes
from hamoon.domains.provider_result.api.schemas import SubmitProviderResultRequest
from hamoon.domains.provider_result.application.handlers import (
    SubmitProviderResultResult,
)
from hamoon.domains.provider_result.domain.entities import ProviderResult

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
PROVIDER = UUID("22222222-2222-2222-2222-222222222222")
REFERRAL = UUID("33333333-3333-3333-3333-333333333333")
HOUSEHOLD = UUID("44444444-4444-4444-4444-444444444444")
INTERVENTION = UUID("55555555-5555-5555-5555-555555555555")
PRESCRIPTION_ITEM = UUID("66666666-6666-6666-6666-666666666666")
RESULT = UUID("77777777-7777-7777-7777-777777777777")
PLAN = UUID("88888888-8888-8888-8888-888888888888")


class _Transaction:
    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, _exc, _tb):
        self._session.committed = exc_type is None
        return False


class _Session:
    def __init__(self) -> None:
        self.committed = False

    def begin(self):
        return _Transaction(self)


def _provider_result(now: datetime) -> ProviderResult:
    return ProviderResult(
        id=RESULT,
        referral_id=REFERRAL,
        provider_id=PROVIDER,
        result_status="COMPLETED",
        result_type="SERVICE_COMPLETION",
        result_summary="Provider says the service completed.",
        result_payload={"provider_metric": "ok"},
        service_started_at=now - timedelta(days=2),
        service_completed_at=now,
        submitted_at=now,
        external_result_id="result-1",
        provider_reference="provider-ref",
        request_hash="a" * 64,
        evidence_ids=(),
    )


def _plan(now: datetime) -> ReassessmentPlan:
    return ReassessmentPlan(
        id=PLAN,
        household_id=HOUSEHOLD,
        intervention_id=INTERVENTION,
        provider_result_id=RESULT,
        prescription_item_id=PRESCRIPTION_ITEM,
        assigned_actor_id=ACTOR,
        review_after_days=30,
        due_at=now + timedelta(days=30),
        policy_version="prescription-item-review-v1",
        workflow_id=f"reassessment:{PLAN}",
        status=ReassessmentPlanStatus.SCHEDULED,
        version=1,
        created_at=now,
        created_by=ACTOR,
    )


@pytest.mark.asyncio
async def test_provider_result_starts_reassessment_after_db_commit_best_effort(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    result = _provider_result(now)
    plan = _plan(now)
    session = _Session()
    settings = object()
    calls = {}

    class _Handler:
        def __init__(self, **_kwargs) -> None:
            pass

        async def handle(self, command):
            calls["command"] = command
            return SubmitProviderResultResult(
                result=result,
                duplicate=False,
                reassessment_plan=plan,
            )

    async def _start(*, plan, settings):
        assert session.committed is True
        calls["plan"] = plan
        calls["settings"] = settings
        return False

    monkeypatch.setattr(routes, "SubmitProviderResultHandler", _Handler)
    monkeypatch.setattr(routes, "start_reassessment_best_effort", _start)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)

    response = await routes.submit_provider_result(
        "ext-ref",
        SubmitProviderResultRequest(
            external_result_id="result-1",
            result_status="COMPLETED",
            result_type="SERVICE_COMPLETION",
            result_summary="Provider says the service completed.",
            result_payload={"provider_metric": "ok"},
            service_started_at=result.service_started_at,
            service_completed_at=result.service_completed_at,
            evidence=[],
            provider_reference="provider-ref",
        ),
        SimpleNamespace(provider_id=PROVIDER, actor_id=ACTOR),
        session,
    )

    assert session.committed is True
    assert calls["plan"] is plan
    assert calls["settings"] is settings
    assert response.data.id == RESULT
    assert response.data.reassessment_plan_id == PLAN
    assert response.data.workflow_id == plan.workflow_id
