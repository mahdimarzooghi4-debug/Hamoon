from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from hamoon.app.observability.json_logging import SafeJsonFormatter
from hamoon.app.security import dependencies, resource_scope
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.oidc import AuthenticatedPrincipal
from hamoon.domains.evidence.api.routes import _ensure_sensitivity_access
from hamoon.domains.evidence.domain.entities import EvidenceSensitivity
from hamoon.domains.family_data.api import routes as family_routes
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.provider_result.application.commands import SubmitProviderResultCommand
from hamoon.domains.provider_result.application.handlers import SubmitProviderResultHandler
from hamoon.domains.provider_result.domain.errors import ProviderResultScopeError
from hamoon.domains.referral.domain.entities import Referral, ReferralStatus

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD = UUID("22222222-2222-2222-2222-222222222222")
PROVIDER = UUID("33333333-3333-3333-3333-333333333333")
REFERRAL_ID = UUID("44444444-4444-4444-4444-444444444444")


def _context(
    *,
    roles: frozenset[Role],
    scopes: frozenset[str] = frozenset(),
) -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR,
        actor_type=ActorType.HUMAN,
        subject="security-regression",
        issuer="integration",
        roles=roles,
        scopes=scopes,
    )


@pytest.mark.asyncio
async def test_unauthorized_household_is_hidden() -> None:
    class Assignments:
        def __init__(self, _session: object) -> None:
            pass

        async def has_active_assignment(
            self,
            *,
            household_id: UUID,
            actor_id: UUID,
        ) -> bool:
            assert household_id == HOUSEHOLD
            assert actor_id == ACTOR
            return False

    original = resource_scope.SqlAlchemyCaseAssignmentRepository
    resource_scope.SqlAlchemyCaseAssignmentRepository = Assignments
    try:
        with pytest.raises(HTTPException) as exc:
            await resource_scope.require_household_assignment(
                session=object(),
                context=_context(roles=frozenset({Role.CASEWORKER})),
                household_id=HOUSEHOLD,
            )
    finally:
        resource_scope.SqlAlchemyCaseAssignmentRepository = original

    assert exc.value.status_code == 404
    assert exc.value.detail == {"code": "RESOURCE_NOT_FOUND"}


class _ProviderScopedReferrals:
    async def get_by_provider_reference(
        self,
        *,
        provider_id: UUID,
        external_referral_id: str,
    ) -> Referral | None:
        if provider_id != PROVIDER or external_referral_id != "external-referral":
            return None
        return Referral(
            id=REFERRAL_ID,
            household_id=HOUSEHOLD,
            intervention_id=UUID("55555555-5555-5555-5555-555555555555"),
            provider_match_id=UUID("66666666-6666-6666-6666-666666666666"),
            provider_selection_id=UUID("77777777-7777-7777-7777-777777777777"),
            provider_id=PROVIDER,
            provider_service_id=UUID("88888888-8888-8888-8888-888888888888"),
            status=ReferralStatus.IN_PROGRESS,
            priority="NORMAL",
            version=3,
            response_due_at=None,
            sent_at=datetime.now(UTC),
            accepted_at=datetime.now(UTC),
            completed_at=None,
            cancelled_at=None,
            external_referral_id="external-referral",
            subject_reference="opaque-subject",
            created_by=ACTOR,
            created_at=datetime.now(UTC),
            data_items=(),
        )


class _Results:
    def __init__(self) -> None:
        self.item = None

    async def add(self, item: object) -> None:
        self.item = item

    async def get_by_external_result(
        self,
        *,
        provider_id: UUID,
        external_result_id: str,
    ):
        return None


class _Recorder:
    async def record(self, _item: object) -> None:
        return None


@pytest.mark.asyncio
async def test_provider_cannot_cross_provider_scope() -> None:
    results = _Results()
    handler = SubmitProviderResultHandler(
        referrals=_ProviderScopedReferrals(),
        results=results,
        events=_Recorder(),
        audits=_Recorder(),
    )

    with pytest.raises(ProviderResultScopeError, match="RESOURCE_NOT_FOUND"):
        await handler.handle(
            SubmitProviderResultCommand(
                provider_id=UUID("99999999-9999-9999-9999-999999999999"),
                actor_id=ACTOR,
                external_referral_id="external-referral",
                external_result_id="cross-provider-result",
                result_status="COMPLETED",
                result_type="SERVICE_COMPLETION",
                result_summary="must remain provider-scoped",
                result_payload=None,
                service_started_at=None,
                service_completed_at=datetime.now(UTC),
                evidence_ids=(),
                provider_reference=None,
                correlation_id="security-regression",
            )
        )

    assert results.item is None


@pytest.mark.asyncio
async def test_ai_service_identity_cannot_enter_human_authority_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = AuthenticatedPrincipal(
        subject="ai-runtime",
        issuer="integration",
        roles=frozenset({Role.AI_RUNTIME}),
        scopes=frozenset(),
        display_name=None,
        organization_id=None,
        unit_id=None,
    )

    async def fake_principal(_credentials: object, _validator: object):
        return principal

    monkeypatch.setattr(dependencies, "_principal", fake_principal)

    with pytest.raises(HTTPException) as exc:
        await dependencies.get_authorization_context(None, object())

    assert exc.value.status_code == 403
    assert exc.value.detail == {"code": "SERVICE_IDENTITY_REQUIRED"}


@pytest.mark.asyncio
async def test_accepted_state_resolution_route_rejects_non_caseworker_authority() -> None:
    route = next(
        item
        for item in family_routes.router.routes
        if isinstance(item, APIRoute)
        and item.path
        == "/api/v1/households/{household_id}/accepted-state/{fact_type}/resolve"
        and "POST" in item.methods
    )
    context_dependency = next(
        item for item in route.dependant.dependencies if item.name == "context"
    )
    guard = context_dependency.call
    assert guard is not None

    with pytest.raises(HTTPException) as exc:
        await guard(_context(roles=frozenset({Role.AI_RUNTIME})))

    assert exc.value.status_code == 403
    assert exc.value.detail == {"code": "FORBIDDEN"}

    allowed = await guard(_context(roles=frozenset({Role.CASEWORKER})))
    assert Role.CASEWORKER in allowed.roles


def test_highly_sensitive_evidence_requires_explicit_scope() -> None:
    with pytest.raises(HTTPException) as exc:
        _ensure_sensitivity_access(
            context=_context(roles=frozenset({Role.CASEWORKER})),
            sensitivity=EvidenceSensitivity.HIGHLY_SENSITIVE,
        )

    assert exc.value.status_code == 404

    _ensure_sensitivity_access(
        context=_context(
            roles=frozenset({Role.CASEWORKER}),
            scopes=frozenset({"evidence.highly_sensitive"}),
        ),
        sensitivity=EvidenceSensitivity.HIGHLY_SENSITIVE,
    )


def test_structured_logs_redact_common_pii_and_secrets() -> None:
    record = logging.LogRecord(
        name="hamoon.security.regression",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=(
            "Authorization=Bearer secret-token "
            "password=hunter2 national_id=1234567890 "
            "contact=jane@example.com phone 09121234567"
        ),
        args=(),
        exc_info=None,
    )
    payload = json.loads(SafeJsonFormatter().format(record))
    rendered = json.dumps(payload, sort_keys=True)

    for forbidden in (
        "secret-token",
        "hunter2",
        "1234567890",
        "jane@example.com",
        "09121234567",
    ):
        assert forbidden not in rendered
