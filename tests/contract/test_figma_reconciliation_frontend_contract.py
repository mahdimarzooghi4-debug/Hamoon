"""Regression guard for the first canonical Figma / live API alignment slice.

This checks wiring and policy boundaries in source. Runtime behavior is separately
covered by existing backend contract tests and frontend TypeScript/CI gates.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_draft_household_creation_wires_the_real_scoped_api() -> None:
    backend = read("src/hamoon/domains/household/api/routes.py")
    api = read("frontend/src/api/households.ts")
    page = read("frontend/src/pages/HouseholdsPage.tsx")

    assert '@router.post("", response_model=CreateHouseholdResponse' in backend
    assert "require_roles(Role.CASEWORKER)" in backend
    assert '"/api/v1/households"' in api
    assert "JSON.stringify({ case_code: caseCode.trim() })" in api
    assert "await createHousehold(caseCode)" in page
    assert "HOUSEHOLD_CASE_CODE_EXISTS" in page
    assert "createdCase.id" in page
    # Identity and PGOR values must never be guessed during DRAFT creation.
    request = api.split("export async function createHousehold(", 1)[1]
    assert "organizational_unit_id:" not in request
    assert "pgor:" not in request


def test_foundation_import_keeps_human_admin_and_draft_boundaries() -> None:
    backend = read("src/hamoon/domains/learning/api/routes.py")
    api = read("frontend/src/api/learningGovernance.ts")
    page = read("frontend/src/pages/LearningGovernancePage.tsx")

    assert '"/api/v1/admin/learning/foundation-datasets/import"' in backend
    assert "ImportApprovedFoundationDatasetHandler" in backend
    assert '"/api/v1/admin/learning/foundation-datasets/import"' in api
    fn = api.split("export async function importFoundationDataset(", 1)[1]
    fn = fn.split("export async function approveLearningDataset(", 1)[0]
    assert '"DIAGNOSIS" | "OUTCOME_INTERPRETATION"' in fn
    assert 'source_version: "v1"' in fn
    assert "approveLearningDataset(" not in fn
    assert "executeInternalTrainingRun(" not in fn
    assert "promoteRoutingPolicy(" not in fn
    assert "foundationAcknowledged" in page
    assert 'dataset.status !== "DRAFT"' in page
    assert 'dataset.source_kind !== "APPROVED_FOUNDATION_SOURCE"' in page


def test_frontend_never_adds_local_password_login() -> None:
    login = read("frontend/src/pages/AccessGatePage.tsx")
    assert "beginLogin(returnTo)" in login
    assert '<input type="password"' not in login
