# Hamoon real-data pilot

Status: **caseworker entry flows are in the release PR; production data collection is not enabled**

## Phase 1: caseworker records and reviews facts

1. A caseworker creates a household draft using the organization-assigned case code. The server assigns the staff member and organizational scope.
2. The caseworker records the household employment status, its source, and when it became true.
3. The caseworker starts a baseline assessment from the active PGOR definition. Each observation records a score, source, and effective time.
4. A staff member validates, disputes, or rejects each fact or observation. Only an explicit human acceptance changes the accepted-state projection.
5. No step in this flow trains a model, creates an ML dataset, or calculates an official PGOR snapshot automatically.

The current entry pages use the existing authenticated APIs and preserve pending validation state. The data-entry flow requires no GPU.

## Current scope and boundary

The repository has household records and household-scoped facts, but no household-member/person entity or API. The initial fact form is therefore deliberately limited to EMPLOYMENT_STATUS; the baseline form uses the active PGOR indicators. Do not enter member names, national identifiers, health details, or free-form case notes into an unrelated fact field.

Additional fields need an approved, versioned catalog that defines their meaning, value type, source requirements, effective-time rules, access scope, and review policy. A caseworker should not invent new fact codes during entry.

## Dataset preparation comes later

Raw submitted facts are not training examples. After a period of caseworker use:

- review and accept records with traceable sources;
- resolve disputed and rejected entries;
- define a de-identification and retention policy for any learning export;
- create a versioned, human-reviewed dataset from suitable records and outcomes;
- evaluate the selected model offline, then require explicit human approval before any production activation.

The Qwen selection is for offline evaluation only. Production inference and automatic training remain disabled.

## Before the real pilot

The current Render service is a static fictional-data demo. Do not direct staff to enter real information there. A real pilot needs an isolated authenticated API and PostgreSQL environment, validated OIDC and household-assignment rules, backups and restore checks, secret configuration, and an agreed data-retention and incident process. Render resources have not been provisioned for Hamoon.
