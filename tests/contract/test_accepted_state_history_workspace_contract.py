"""Figma correction history is backed by persisted human acceptance decisions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_history_ui_uses_scoped_api_and_version_cursor() -> None:
    api = read("frontend/src/api/familyData.ts")
    component = read("frontend/src/components/AcceptedStateHistory.tsx")
    page = read("frontend/src/pages/HouseholdFactsPage.tsx")
    assert '"/accepted-state/" + encodeURIComponent(factType)' in api
    assert 'query.set("before_version", String(beforeVersion))' in api
    assert 'getAcceptedHistory(householdId, factType, cursor)' in component
    assert "response.next_before_version" in component
    assert "generation === generationRef.current" in component
    assert "item.reason_code" in component
    assert "item.reason_text" in component
    assert "item.changed_by" in component
    assert "item.previous_fact_id" in component
    assert "item.new_fact_id" in component
    assert "item.domain_event_id" in component
    assert "AcceptedStateHistoryPanel" in page
    assert "refreshToken={historyRevision}" in page


def test_history_read_model_does_not_mutate_pgor_or_fact_validation() -> None:
    repo = read("src/hamoon/domains/family_data/infrastructure/repositories.py")
    route = read("src/hamoon/domains/family_data/api/routes.py")
    block = route.split("async def get_accepted_state_history(", 1)[1].split(
        '@router.post(', 1
    )[0]
    assert "require_household_assignment(" in block
    assert "SqlAlchemyAcceptedStateRepository(" in block
    assert ".list_history(" in block
    assert "set_current(" not in block
    assert "calculate_pgor(" not in block
    assert "AcceptedStateChangeModel.household_id == household_id" in repo
    assert "AcceptedStateChangeModel.fact_type == fact_type" in repo
    assert "limit(limit + 1)" in repo
