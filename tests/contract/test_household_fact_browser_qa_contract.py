"""The browser QA must exercise real local OIDC and authorized backend, never mock access."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_authenticated_browser_qa_is_wired_after_real_stack_readiness() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    browser = (ROOT / "frontend/scripts/household-facts-browser.test.mjs").read_text(
        encoding="utf-8"
    )
    package = (ROOT / "frontend/package.json").read_text(encoding="utf-8")
    assert "playwright" in package
    assert "test:browser" in package
    assert "npx playwright install --with-deps chromium" in ci
    assert "Authenticated Chromium correction QA" in ci
    assert ci.index("Wait for local services") < ci.index("Authenticated Chromium correction QA")
    assert ci.index("Authenticated Chromium correction QA") < ci.index("Stop complete local stack")
    assert "protocol/openid-connect/token" in browser
    assert "role-mappings/realm" in browser
    assert 'page.locator("#kc-login").click()' in browser
    assert "sessionStorage.getItem" in browser
    assert "supersedes_fact_id" in browser
    assert "expected_accepted_projection_version" in browser
    assert "assertNoHorizontalOverflow" in browser
    assert "expected: 409" in browser
    assert "expected: 404" in browser
    assert "page.route(" not in browser
    assert "addInitScript" not in browser
    assert "directAccessGrantsEnabled" not in browser



def test_figma_right_sheet_geometry_is_asserted_without_mock_data() -> None:
    browser = (ROOT / "frontend/scripts/household-facts-browser.test.mjs").read_text(
        encoding="utf-8"
    )
    page = (ROOT / "frontend/src/pages/HouseholdFactsPage.tsx").read_text(
        encoding="utf-8"
    )
    overlay = (ROOT / "frontend/src/pages/HouseholdFactsOverlayPage.tsx").read_text(
        encoding="utf-8"
    )
    css = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
    assert 'data-figma-panel="correction-right-sheet"' in page
    assert 'className="fact-context"' not in page
    assert 'className="fact-route__dialog"' in overlay
    assert "<HouseholdPage householdId={householdId} />" in overlay
    assert "state.household.case_code" in page
    assert "current.accepted_value" in page
    assert "assertCorrectionSheetLayout(page, \"desktop\")" in browser
    assert "assertCorrectionSheetLayout(page, \"mobile\")" in browser
    assert "width: min(920px, 100vw)" in css
    assert "page.route(" not in browser
