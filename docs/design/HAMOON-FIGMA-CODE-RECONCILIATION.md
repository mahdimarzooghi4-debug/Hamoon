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
| `55:176` Login | `auth/oidc.ts`, `pages/AccessGatePage.tsx` | Functional OIDC match; local-login mock in Figma NOT authorized |
| `23:3020` Home | `pages/HomePage.tsx`, `layout/AppShell.tsx` | Functional data, visual mismatch; never render decorative threshold labels as policy |
| `31:1661`, `31:1993` Work queue / detail | `pages/WorkQueuePage.tsx` | Queue+claim implemented; drawer parity pending |
| `31:4556`, `31:4896` Cases / preview | `pages/HouseholdsPage.tsx` | Read/preview implemented |
| `59:5703`, `59:5897`, `59:6131` Case creation | `pages/HouseholdsPage.tsx` + `api/households.ts` | **Slice 1:** server-scoped draft case creation only; members/identity/observations remain out of this endpoint |
| `37:5908` through `37:6493` Data correction | — | Missing canonical correction flow; separate authoritative fact/accepted-state contracts required |
| `77:70` Evidence | — | UI not implemented; private evidence/scanning flow cannot be simulated |
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
1. Reconcile Figma login visual with OIDC-only security boundary (no local-login form).
2. Make case onboarding stages 2/3 only after inspecting authoritative identity, member, observation, evidence and human-acceptance contracts.
3. Implement data correction and evidence workspace after API/role/security review.
4. Align dashboard layout, brand asset, responsive styles, canonical drawers, and all real API Loading/Empty/Error/Forbidden/409 states.
5. Run browser screenshot comparisons at representative desktop/mobile viewports. Static source review and CI frontend build are necessary but not sufficient for visual acceptance.

No Production deployment, Stage/Release gates, model promotion, or Figma LEGACY revival is authorized by this document.
