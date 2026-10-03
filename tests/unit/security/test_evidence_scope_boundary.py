from uuid import UUID

import pytest
from fastapi import HTTPException

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.evidence.api.routes import _ensure_sensitivity_access
from hamoon.domains.evidence.domain.entities import EvidenceSensitivity
from hamoon.domains.identity.domain.entities import ActorType

ACTOR = UUID("11111111-1111-1111-1111-111111111111")


def _context(scopes: frozenset[str]) -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR,
        actor_type=ActorType.HUMAN,
        subject="subject",
        issuer="issuer",
        roles=frozenset({Role.CASEWORKER}),
        scopes=scopes,
    )


def test_highly_sensitive_evidence_requires_explicit_scope() -> None:
    with pytest.raises(HTTPException) as exc:
        _ensure_sensitivity_access(
            context=_context(frozenset()),
            sensitivity=EvidenceSensitivity.HIGHLY_SENSITIVE,
        )
    assert exc.value.status_code == 404

    _ensure_sensitivity_access(
        context=_context(frozenset({"evidence.highly_sensitive"})),
        sensitivity=EvidenceSensitivity.HIGHLY_SENSITIVE,
    )


def test_standard_sensitive_evidence_uses_case_scope_only() -> None:
    _ensure_sensitivity_access(
        context=_context(frozenset()),
        sensitivity=EvidenceSensitivity.SENSITIVE_PERSONAL,
    )
