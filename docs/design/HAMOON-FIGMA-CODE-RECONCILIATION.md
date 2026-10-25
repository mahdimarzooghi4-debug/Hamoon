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
| `23:3020` Home | `pages/HomePage.tsx`, `layout/AppShell.tsx` | Functional data, visual mismatch; never render decorative threshold labels as policy |
| `31:1661`, `31:1993` Work queue / detail | `pages/WorkQueuePage.tsx` | Queue+claim implemented; drawer parity pending |
| `31:4556`, `31:4896` Cases / preview | `pages/HouseholdsPage.tsx` | Read/preview implemented |
| `59:5703`, `59:5897`, `59:6131` Case creation | `pages/HouseholdsPage.tsx` + `api/households.ts` | **Slice 1:** server-scoped draft case creation only; members/identity/observations remain out of this endpoint |
| `37:5908` through `37:6493` Data correction | `pages/HouseholdFactsPage.tsx`, `components/AcceptedStateHistory.tsx`, `api/familyData.ts` | **Slices 3–4:** current accepted fact, new PENDING fact, human validation/resolve, and paginated persisted acceptance-decision history; visual parity and fact supersession lineage not claimed |
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
3. Data correction has a first backend-led workspace. Full correction lineage (supersedes_fact_id), historical PGOR impact and final Figma drawer parity remain open. Evidence UI exists; browser screenshot/pixel comparison and production scanner/storage configuration validation remain release gates.
4. Align dashboard layout, brand asset, responsive styles, canonical drawers, and all real API Loading/Empty/Error/Forbidden/409 states.
5. Run browser screenshot comparisons at representative desktop/mobile viewports. Static source review and CI frontend build are necessary but not sufficient for visual acceptance.

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
- Adds read-only, CASEWORKER-and-household-assignment-scoped GET `/api/v1/households/{id}/accepted-state/{fact_type}/history` backed by existing `accepted_state_change` rows. SQL filters by household and fact type before bounded pagination (1..100, default 50), with version cursor.
- Displays actual previous/new fact identifiers, known values from existing household facts, persisted human reason code/text, actor identifier, decision time and domain-event identifier. No invented names or inferred reason if absent.
- Accepted State history is not the same as the `supersedes_fact_id` fact lineage or the validation state machine. A historical accepted version is not automatically marked SUPERSEDED. No automatic PGOR recalculation.
- No new database migration, acceptance rule, or write command. The screen still requires authorized authenticated browser comparison to claim full Figma parity.
