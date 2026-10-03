from uuid import UUID

import pytest
from fastapi import HTTPException

from hamoon.app.security import dependencies
from hamoon.app.security.context import Role
from hamoon.app.security.oidc import AuthenticatedPrincipal

ACTOR = UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_service_role_is_rejected_from_human_context(monkeypatch) -> None:
    principal = AuthenticatedPrincipal(
        subject="service-runtime",
        issuer="issuer",
        roles=frozenset({Role.AI_RUNTIME}),
        scopes=frozenset(),
        display_name=None,
        organization_id=None,
        unit_id=None,
    )

    async def fake_principal(_credentials, _validator):
        return principal

    monkeypatch.setattr(dependencies, "_principal", fake_principal)

    with pytest.raises(HTTPException) as exc:
        await dependencies.get_authorization_context(None, object())

    assert exc.value.status_code == 403
    assert exc.value.detail == {"code": "SERVICE_IDENTITY_REQUIRED"}
