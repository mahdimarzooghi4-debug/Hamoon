# Hamoon — Figma ↔ Code Reconciliation
Status: **SLICE 1 IMPLEMENTED; broader reconciliation OPEN**
Figma source: https://www.figma.com/design/4NAZskhPh0nYlIII8jgksG
Canonical product guide: page `120:2` (only listed canonical frames, not LEGACY).
Baseline: `main` @ `586103470739110229264d49e2d2ac45975ae991`

## Rule of authority
1. Canonical Figma defines approved UI composition, NOT new Backend policies or data.
2. Backend contract, source governance, authorization, Accepted State and PGOR invariants remain authoritative.
3. Only live API data may be used. No hardcoded person records, guessed demographics, fabricated referrals, outcomes or scores.
4. Figma `LEGACY` frames (`34:7878`, `34:8058`, `48:3901`, `40:14614`) are not implementation targets.
5. Do not expose credentials or implement the local username/password mock on Figma login frame `55:176`; actual login is OIDC Authorization Code + PKCE.

## Code reconciliation matrix

| Canonical frame(s) | React location | Status |
| --- | --- | --- |
| `55:176` Login | `auth/oidc.ts`, `pages/AccessGatePage.tsx` | OIDC-only canonical design reconciled 2026-10-24; local credential mock hidden |
| `23:3020` Home | `pages/HomePage.tsx`, `layout/AppShell.tsx` | Dashboard uses live household/work-queue data; shell header now matches the frame’s profile-triggered role navigation and right-aligned brand lockup. The inline SVG mark is a code-drawn approximation, not the original Figma export; settings/notification controls and screenshot comparison remain open. Never render decorative threshold labels as policy |
| `31:1661`, `31:1993` Work queue / detail | `pages/WorkQueuePage.tsx` | Queue hierarchy, filters, search, live overdue/upcoming summaries, and a read-only detail drawer with supported claim/household navigation; Figma follow-up note/defer/result actions remain blocked on backend contracts |
| `31:4556`, `31:4896` Cases / preview | `pages/HouseholdsPage.tsx` | Read/preview implemented |
| `59:5703`, `59:5897`, `59:6131` Case creation | `pages/HouseholdsPage.tsx` + `api/households.ts` | **Slice 1:** server-scoped draft case creation only; members/identity/observations remain out of this endpoint |
| `37:5908` through `37:6493` Data correction | `pages/HouseholdFactsPage.tsx`, `components/AcceptedStateHistory.tsx`, `api/familyData.ts` | **Slices 3–5:** current accepted fact, linked PENDING correction with persisted reason and explicit source version, human validation/resolve, and paginated persisted acceptance-decision history; visual parity and historical PGOR impact not claimed |
| `77:70` Evidence | `pages/HouseholdEvidencePage.tsx`, `api/evidence.ts`, `domains/evidence/api/routes.py` | **Slice 2:** private listing, upload-init/content/finalize, SHA-256 verification, scan/quarantine state, and capability-based download; highly-sensitive rows are omitted without scope |
| `29:2244` Household detail | `pages/HouseholdPage.tsx` | Read workspace implemented; visual parity pending |
| `40:4302` through `40:5016` Diagnosis | `components/DiagnosisSection.tsx` | Functional proposals, human decision and history |
| `40:10287` through `40:11143` Prescription | `components/PrescriptionSection.tsx` | Functional proposals, review, interventions and history |
| `105:126`, `48:3335` through `48:3692` Referral | `components/ProviderReferralSection.tsx` | Functional policy eligibility, human selection and referral |
| `40:14342`, `40:14487`, `34:7397`, `34:7607` | `components/OutcomeMeasurementSection.tsx` | Functional provider result, reassessment and PGOR; validate visuals |
| `98:77`, `98:231`, `40:14794` | `components/OutcomeMeasurementSection.tsx` | Human Outcome review and resulting timeline |
| `40:21713` Admin dashboard | `pages/AdminHealthPage.tsx`, `pages/EmpowermentOverviewPage.tsx` | Separated authorized read models; no unapproved nationwide aggregate |
| `87:35`, `88:191`, `92:127`, `92:383` | `pages/LearningGovernancePage.tsx` | Governance + explicit promotion; **Slice 1:** source-attested Foundation v1 DRAFT import |

## Slice 1 backend contracts
- `POST /api/v1/households` is restricted to `CASEWORKER`, requires a nonempty unique `case_code` (max 100). The server binds actor, unit scope and creates a `DRAFT` case and primary assignment. A duplicate yields `409 HOUSEHOLD_CASE_CODE_EXISTS`. No family identity or accepted observations can be fabricated.
- `POST /api/v1/admin/learning/foundation-datasets/import` is restricted to `ADMIN`, accepts approved source `v1` for `DIAGNOSIS` or `OUTCOME_INTERPRETATION` only, re-attests source package and creates `DRAFT` runtime Dataset. Separate ADMIN Dataset Approval and all Training/Evaluation/Promotion controls remain required.
- The approved Foundation source is not an operational LearningSignal. `PRESCRIPTION` Foundation remains deferred.
- No Backend endpoints or policy rules are invented in this slice.

## Remaining hard blockers / follow-up
1. COMPLETE on 2026-10-24: canonical login frame `55:176` now hides divider `55:212`, local credentials `55:216` and obsolete mock errors `55:235`; subtitle `55:205` explicitly states OIDC-only. Screenshot visually checked. No password handling added to app.
2. Make case onboarding stages 2/3 only after inspecting authoritative identity, member, observation, evidence and human-acceptance contracts.
3. Data correction has a backend-led workspace with linked correction lineage. Historical PGOR impact analysis and final Figma drawer parity remain open. Evidence UI exists; browser screenshot/pixel comparison and production scanner/storage configuration validation remain release gates.
4. Finish Home settings/notification actions and replace the drawn brand approximation with the approved export when the durable asset is available; complete desktop/mobile screenshot comparison and remaining API Loading/Empty/Error/Forbidden/409 states. The Home dashboard structure is in draft PR #23, but is not visually accepted until browser comparison.
5. Run browser screenshot comparisons at representative desktop/mobile viewports. Static source review and CI frontend build are necessary but not sufficient for visual acceptance.
6. Define authorized backend contracts for work-item follow-up notes, deferral and result recording before implementing the corresponding controls shown in the Work Queue detail frame. Do not simulate these actions in the frontend.

No Production deployment, Stage/Release gates, model promotion, or Figma LEGACY revival is authorized by this document.


## Slice 2 — Evidence workspace (Draft PR #15)
- Canonical Figma evidence frame: `77:70`.
- Added household-scoped GET list endpoint. The repository filters `HIGHLY_SENSITIVE` records in SQL before applying the limit unless the actor has `evidence.highly_sensitive`.
- Added RTL evidence workspace route `/households/{household_id}/evidence`, linked from the household detail page.
- Upload flow uses the existing short-lived single-use upload capability, computes SHA-256 in the browser, invokes server finalization/scanning, and refreshes actual backend state.
- Download action is only offered for `AVAILABLE + CLEAN`; the server independently checks sensitivity scope and signed capability and refuses content unless lifecycle is AVAILABLE.
- Upload uses the server-configured API allowlist, with a matching 10 MiB UI ceiling aligned to the current backend default. Runtime policy changes must keep both values synchronized.
- Tests cover route scope propagation, SQL sensitivity filtering, and the UI's fail-closed download boundary.
- This slice does not implement data correction, evidence deletion/archive actions, drag-and-drop, or release approval. Browser visual regression remains unverified until an authenticated test environment is available.


## Slice 3 — Human-reviewed household facts workspace (Draft)
- Canonical Figma frames: 37:5908 selection, 37:6098 corrected value and reason, 37:6288 impact/confirmation, 37:6493 history.
- Uses existing CASEWORKER household-scoped family-data API. Sources, facts and current accepted state come from real read models.
- New fact is PENDING_VALIDATION; human validation requires expected_validation_version; only VALIDATED facts can be explicitly selected into Accepted State with expected_projection_version.
- Current accepted value is never overwritten on initial recording. Old facts remain in history. supersedes_fact_id is NOT written by this UI because the current POST contract does not expose it; complete correction lineage remains open.
- No client PGOR/E recomputation, AI acceptance, fabricated identity, guessed source, automatic validation, automatic supersession or provider selection.
- Figma sample identity/employment/numbers are display-only, never runtime data. Browser parity and authorized end-to-end QA remain release gates.


## Slice 4 — Accepted State decision history (Figma 37:6493)
- Adds read-only, CASEWORKER-and-household-assignment-scoped GET `/api/v1/households/{id}/accepted-state/{fact_type}/history` backed by existing `accepted_state_change` rows. SQL filters by household and fact type before bounded pagination (1..100, default 50), with composite (version, change-ID) cursor.
- Displays actual previous/new fact identifiers, known values from existing household facts, persisted human reason code/text, actor identifier, decision time and domain-event identifier. No invented names or inferred reason if absent.
- Accepted State history is not the same as the `supersedes_fact_id` fact lineage or the validation state machine. A historical accepted version is not automatically marked SUPERSEDED. No automatic PGOR recalculation.
- No new database migration, acceptance rule, or write command. The screen still requires authorized authenticated browser comparison to claim full Figma parity.


## Slice 5 — Persisted fact correction lineage (Figma 37:6098 / 37:6493)
- The existing `household_fact.supersedes_fact_id` foreign key now binds a proposed correction to the explicitly selected **current Accepted Fact** of the same household, fact type and value type. The caller supplies the observed Accepted State projection version; a stale version or changed accepted fact fails with 409, wrong-household references are hidden as 404, and incompatible type fails with 422.
- The correction reason code/text are persisted on the new fact using migration `20261025_0039` and read only through the existing assigned-household facts endpoint. The reason code and prior fact identifier also appear in the domain event and audit metadata; free-text reason is not copied to general audit metadata.
- Existing unlinked fact-record clients remain supported. Linked correction requires the reference, expected version and nonblank reason together; no fabricated data or implicit supersession. The old fact remains unchanged; the new fact starts PENDING_VALIDATION and requires separate human validation and Accepted State resolution.
- The UI sends the real accepted fact ID and projection version and renders stored lineage/reason. An Accepted State change that races with the record request may still require re-review: no automatic acceptance or PGOR recalculation is permitted. Authenticated browser visual comparison is still pending.


## Slice 6 — Authenticated Chromium correction QA (local CI, not Stage)
- CI release-artifact smoke now starts the real local stack, then provisions temporary, random synthetic CASEWORKER identities in the **local Keycloak realm** via the admin API (never the Production realm). Chromium performs actual Authorization Code + PKCE login. No injected bearer token, mocked API response, direct-grant login, or invented Production credential.
- Using the authenticated API, the browser suite creates an isolated synthetic DRAFT household and an initial fact; a human-equivalent explicit validation and Accepted State selection seed the correction precondition. The UI then records a linked correction, checks the original Accepted State stays unchanged, validates separately, and confirms explicit human acceptance. It also verifies stale-version 409 and unauthorized cross-caseworker masked 404.
- Screenshots of the **synthetic-only** correction UI at 1440px desktop and 390px mobile are retained as short-lived CI artifacts. A horizontal overflow check runs at both widths. This is browser functional/layout QA; it is **not** pixel-by-pixel Figma parity or real-data acceptance. Reference frames: `37:5908`, `37:6098`, `37:6288`, `37:6493`.
- The local browser fixture deletes temporary Keycloak identities after the test and the CI stack is destroyed with volumes. If local Keycloak admin provisioning, real OIDC or API authorization fails, CI fails closed. Stage/Production are not invoked.


## Slice 6 browser QA findings — backend regressions discovered and fixed
- Real PKCE login exposed a Keycloak first-login required-profile action. The local-only synthetic test user now includes first name, last name and an `example.invalid` email verified by the isolated test realm administrator. No real identity, email delivery or direct access grant is used.
- The first real PostgreSQL household creation failed when the ORM flushed `case_assignment` before its independent `household` parent. `SqlAlchemyHouseholdRepository.add` now explicitly flushes the parent **inside the same caller-owned transaction**, preserving rollback atomicity and enabling FK-safe assignment.
- Simultaneous initial authorized requests for the same OIDC subject caused a duplicate `user_account(issuer, subject)` insert. Human identity provisioning now acquires a PostgreSQL transaction-scoped, SHA-256-derived advisory lock for the issuer+subject **before** checking or creating the account; no global mutex, no duplicate actor, and no auto-authorization beyond the verified OIDC roles.
- New real-PostgreSQL integration tests exercise the household parent/assignment commit and concurrent first-time identity provisioning. Browser CI remains a required gate; screenshots and parity are not claimed until the run succeeds.


## Slice 7 — Figma reference comparison and right-sheet structure (37:6098)
- Reference was inspected as a 1440 × 1280 Figma frame, including a roughly 920 px **right-side correction sheet** atop a dimmed household context. Previous CI Chromium screenshot was a **full-width 1440 px correction page**, with independently stacked long panels. These are demonstrable structural differences; no pixel-level parity is claimed.
- The authenticated correction workspace is now a right-aligned ~920 px content sheet on desktop with a dark, read-only context panel at left. Context displays **only** the actual household case code, lifecycle state, household version, accepted-type count and optional selected Accepted Fact. It does **not** invent Figma mock identities, PGOR/E, referrals or evidence.
- The existing form, separate human validation/acceptance, history, real data sources, reason persistence, authorization and API calls are unchanged. This is UI structure and visual hierarchy only, not a new business policy or API endpoint.
- For viewports <= 980 px, context is hidden and the sheet fills the viewport, with readable mobile stacking <= 600 px. Chromium now checks right-sheet and context geometry at desktop 1440 px and full-width/hidden-context behavior at mobile 390 px, in addition to actual OIDC, lifecycle and horizontal overflow.
- Known gaps: Figma's true underlying household canvas and source-evidence attachment controls are **not** recreated because no equivalent safe interface is established by this slice; a real drawer overlay and screenshot-level/pixel-level matching remain open. Figma sample numbers/people are never operational values; semantic comparison is more reliable than raw pixel scoring on synthetic data.


## Slice 8 — true route-addressable correction overlay above real household page
- Replaces the earlier synthetic read-only left context with the **actual** `HouseholdPage` as the background of the `/households/{id}/facts` route. The household screen uses its authorized read-model APIs and displays only known snapshot/intervention/work-item values or explicit empty states.
- The correction UI is a fixed, independently scrollable right-side sheet above a dimmed inert household view on desktop; on mobile it spans the full viewport below the actual header. The sheet retains the direct navigable URL for bookmarks and browser reload, with explicit close and Escape returning to the household route.
- Background and topbar are inert/inaccessible while dialog is open; a focus trap and initial focus protect keyboard operation. Original focusability, header attributes and body scroll are restored on unmount. Escape/close are ignored while the correction mutation is in progress.
- CI Chromium uses actual OIDC PKCE and PostgreSQL; it opens from the real household page, checks background canvas, inert semantics, modal geometry at 1440px/390px, Escape/explicit close, direct-link reload, record/validation/acceptance and unauthorized access. No fabricated Figma values or Production credential is involved.
- Limitations: not pixel-perfect Figma, not a medical or evidence-upload interface, not a new business/PGOR rule. Stage and Production remain separate release gates.


## Slice 9 — Home dashboard structure (Draft PR #23)
- Canonical frame: `23:3020`. The former generic hero, metric strip and work-queue-only panel are replaced with the Figma hierarchy: case search and journey panel, four live summary cards, a compact task strip, and a household table beside the overview card.
- Household rows and search use the existing assignment-scoped households API; task tiles use the authenticated work queue API. No sample identity, score, household name or outcome is hardcoded. Official E is shown only where the returned household summary contains a PGOR snapshot.
- Summary cards are labelled as counts from returned lists (bounded to the existing API page size), not as national or unbounded totals. Journey threshold values remain absent because Figma decorative values are not policy.
- Loading, auth-required, API-error, empty and dedicated 403/forbidden states are handled. Pixel-level desktop/mobile browser comparison, app header/navigation/brand asset parity, and final visual acceptance remain open.
