# Hamoon — Production Rollback

Status: rollback governance and runtime verification gates implemented. A real rollback is not claimed until the hosted Production runtime is externally changed and the verification gate succeeds.

## Safety model

Rollback reuses a previously built, scanned, Stage-admitted and explicitly human-approved immutable release. It never rebuilds the rollback target and never authorizes a destructive database downgrade.

The database strategy is deliberately:

```text
KEEP_FORWARD_SCHEMA
```

The pre-rollback Production migration identity is captured at admission time and must remain identical after the application rollback. If an older application cannot run against the current forward schema, rollback verification fails and no `rollback_deployed=true` evidence can be produced.

## Production Rollback Admission

The manual `Production Rollback Admission` workflow requires:

- exact current and target commit SHAs;
- current commit backed by a successful Production Verification artifact;
- target commit to be an ancestor of the current commit on `main`;
- target release bundle, Stage Admission and explicit Release Approval to all verify again;
- explicit human `ROLLBACK` confirmation;
- a new expected rollback deployment ID;
- a change/incident reference and rollback reason;
- preservation of the current Production database migration identity.

Its immutable evidence intentionally records:

```text
authorization_only=true
rollback_deployed=false
database_strategy=KEEP_FORWARD_SCHEMA
database_downgrade_authorized=false
```

Admission is authorization, not evidence that Production has changed.

## External deployment boundary

Hamoon does not fabricate a hosting provider or deployment action. After admission, the selected platform/operator must deploy the exact admitted backend and frontend images under the new rollback deployment ID without running a database downgrade.

## Production Rollback Verification

After the real external rollback, the manual `Production Rollback Verification` workflow probes the admitted HTTPS Production endpoint and requires:

- backend commit = exact rollback target commit;
- frontend commit = exact rollback target commit;
- backend/frontend image IDs = exact admitted target images;
- deployment ID = exact expected rollback deployment ID;
- backend readiness and frontend runtime availability;
- protected `/metrics` remains unauthenticated with `401`;
- database migration versions remain exactly equal to the pre-rollback Production migration identity.

Only this workflow can produce evidence with:

```text
rollback_deployed=true
runtime_identity_verified=true
database_schema_preserved=true
database_downgrade_performed=false
status=VERIFIED
```

## Failure rule

If runtime identity differs, readiness fails, or the migration identity changes, the rollback is not verified. The workflow must not reinterpret a partially successful deployment as a successful rollback.

## Scope boundary

These gates do not prove that a hosting provider has actually executed a rollback until the external deployment occurs. They also do not authorize database downgrade, restore, PITR or destructive migration. Database recovery remains governed by the separate Production Recovery Verification path.
