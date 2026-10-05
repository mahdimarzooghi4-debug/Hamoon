# Hamoon — Caseworker Work Queue

Status: PB-101 implemented as an authorization-scoped operational projection.

## Task types

The queue supports the product task types:

- `DIAGNOSIS_REVIEW`
- `PRESCRIPTION_REVIEW`
- `REFERRAL_FOLLOWUP`
- `REASSESSMENT_DUE`
- `OUTCOME_REVIEW`
- `DATA_COMPLETION`
- `CONFLICT_RESOLUTION`

`AI_FALLBACK` remains an operational task type. Legacy `REASSESSMENT` rows remain readable during migration, but new due tasks use `REASSESSMENT_DUE`.

## Authorization boundary

`GET /api/v1/work-queue` is not an actor-id-only lookup.

A task is visible only when:

1. the requesting caseworker has an active `case_assignment` for the task household; and
2. the task is unassigned, assigned to the requesting actor, or already claimed by the requesting actor; and
3. the task is in a requested visible status.

Unassigned tasks are therefore discoverable only inside the caller's authorized household scope. Claiming a task sets its operational owner.

## Source linkage and idempotency

Every projected task stores:

- `household_id`
- `work_type`
- `resource_type`
- `resource_id`
- status/version
- optional due time
- optional policy version

Work items are unique by `(work_type, resource_type, resource_id)`. Repeated delivery of the same source transition therefore cannot create duplicate operational tasks.

## Creation and completion map

| Source transition | Work item |
| --- | --- |
| AI diagnosis persisted as `UNDER_REVIEW` | `DIAGNOSIS_REVIEW` |
| Diagnosis receives a non-DEFER human decision | source task completes |
| AI prescription persisted as `UNDER_REVIEW` | `PRESCRIPTION_REVIEW` |
| Prescription receives a non-DEFER human decision | source task completes |
| Provider response deadline expires | `REFERRAL_FOLLOWUP` |
| Reassessment timer becomes due | `REASSESSMENT_DUE` |
| Outcome review becomes ready | `OUTCOME_REVIEW` |
| Outcome review completes | source task completes |
| PGOR calculation is blocked by missing required indicators | `DATA_COMPLETION` |
| PGOR calculation later succeeds for that assessment | source task completes |
| Observation validation becomes `DISPUTED` | `CONFLICT_RESOLUTION` |
| Disputed observation is validated/rejected/superseded | source task completes |
| Household fact validation becomes `DISPUTED` | `CONFLICT_RESOLUTION` |
| Disputed household fact is validated/rejected/superseded | source task completes |

Human review remains the domain authority. Completing a source entity closes its queue projection even if the task had previously been claimed by another caseworker; the queue must never remain stale after the authoritative domain transition.

## Due / overdue contract

The API returns both `due_at` and server-calculated `is_overdue`. A task is overdue only when its due timestamp is in the past and its status is still `OPEN` or `CLAIMED`.

The repository orders visible tasks by priority, then due time, then creation time, and supports a `due_before` filter.

## Events and audit

Task projection emits:

- `WorkItemCreated`
- `WorkItemCompleted`

Existing specialized reassessment/referral/outcome work-item events remain valid. Task creation/completion is audited under `CASEWORKER_WORK_QUEUE`.

The task is an operational projection. It never replaces the source domain entity, human decision, PGOR snapshot, referral, or outcome.
