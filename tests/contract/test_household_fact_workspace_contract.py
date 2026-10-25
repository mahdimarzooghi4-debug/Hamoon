"""Family-data UI contract regression against the existing human-governed API."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_fact_workspace_calls_only_existing_authoritative_routes() -> None:
    api = read("frontend/src/api/familyData.ts")
    backend = read("src/hamoon/domains/family_data/api/routes.py")
    page = read("frontend/src/pages/HouseholdFactsPage.tsx")
    app = read("frontend/src/app/App.tsx")
    household = read("frontend/src/pages/HouseholdPage.tsx")

    for path in ('"/api/v1/data-sources"', '"/facts"', '"/accepted-state"', '"/validation"', '"/resolve"'):
        assert path in api
    assert '"/api/v1/households/{household_id}/facts"' in backend
    assert '"/api/v1/households/{household_id}/accepted-state"' in backend
    assert "require_household_assignment" in backend
    assert "expected_validation_version: fact.validation_version" in api
    assert "expected_projection_version: expectedProjectionVersion" in api
    assert 'to_status: toStatus' in api
    assert 'fact_id: fact.id' in api
    assert '"PENDING_VALIDATION"' in page
    assert 'fact.validation_status === "VALIDATED" && !isCurrent' in page
    assert "confirmResolve" in page
    assert "parseValue(oldFact.value_type, rawValue)" in page
    assert 'path.endsWith("/facts")' in app
    assert "اصلاح و اعتبارسنجی اطلاعات" in household


def test_fact_record_does_not_auto_validate_or_auto_accept() -> None:
    api = read("frontend/src/api/familyData.ts")
    page = read("frontend/src/pages/HouseholdFactsPage.tsx")
    record = api.split("export async function recordHouseholdFact(", 1)[1].split(
        "export async function changeFactValidation(", 1
    )[0]
    assert "changeFactValidation(" not in record
    assert "resolveAcceptedFact(" not in record
    submit = page.split("function submitRecord(", 1)[1].split(
        'if (state.kind === "loading")', 1
    )[0]
    assert "recordHouseholdFact(" in submit
    assert "changeFactValidation(" not in submit
    assert "resolveAcceptedFact(" not in submit
    assert "supersedes_fact_id: current.fact_id" in page
    assert "expected_accepted_projection_version: current.projection_version" in page
    assert "correction_reason_code: reasonCode" in page
    assert "correction_reason_text: reasonText.trim()" in page
    assert "supersedes_fact_id" in api
    assert "calculatePGOR" not in page


def test_correction_lineage_is_readable_and_does_not_implicitly_change_acceptance() -> None:
    page = read("frontend/src/pages/HouseholdFactsPage.tsx")
    api = read("frontend/src/api/familyData.ts")
    handler = read("src/hamoon/domains/family_data/application/handlers.py")
    assert "fact.supersedes_fact_id" in page
    assert "fact.correction_reason_text" in page
    assert "correction_reason_code: string | null" in api
    assert "correction_reason_text: string | null" in api
    assert "supersedes_fact_id=command.supersedes_fact_id" in handler
    record = handler.split("class RecordHouseholdFactHandler:", 1)[1].split("class ChangeFactValidationHandler:", 1)[0]
    assert "ResolveAcceptedFactHandler(" not in record
    assert "FactValidationStatus.PENDING_VALIDATION" in record
    assert "PGOR" not in record
