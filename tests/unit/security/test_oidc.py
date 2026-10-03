import pytest

from hamoon.app.security.context import Role
from hamoon.app.security.oidc import TokenValidationError, principal_from_claims


def test_keycloak_realm_roles_map_to_hamoon_roles() -> None:
    principal = principal_from_claims(
        {
            "sub": "subject-1",
            "iss": "https://idp.example/realms/hamoon",
            "preferred_username": "caseworker_test",
            "realm_access": {"roles": ["CASEWORKER", "offline_access"]},
            "scope": "openid profile hamoon.read",
            "organization_id": "org-1",
            "unit_id": "unit-12",
        }
    )

    assert principal.roles == frozenset({Role.CASEWORKER})
    assert "hamoon.read" in principal.scopes
    assert principal.unit_id == "unit-12"


def test_missing_subject_is_rejected() -> None:
    with pytest.raises(TokenValidationError):
        principal_from_claims(
            {
                "iss": "https://idp.example/realms/hamoon",
                "realm_access": {"roles": ["CASEWORKER"]},
            }
        )
