# Hamoon — Provider Referral Workflow

Status: provider-neutral outbound referral runtime and durable Temporal orchestration are implemented. Real provider sandbox/Production endpoints and credentials remain environment-specific external evidence and are not claimed by repository tests.

## Runtime chain

```text
Human Provider Selection
→ Referral READY
→ Caseworker Send + explicit data-sharing authorization
→ ReferralDispatch PENDING
→ HamoonReferralWorkflow
→ provider dispatch activity
→ remote HTTPS Provider endpoint
→ ReferralDispatch SENT
→ authenticated Provider callback/result
→ workflow signal
→ downstream Provider Result / reassessment path
```

Provider selection remains human-only. The workflow never chooses a provider and receives only the already-authorized referral and dispatch identifiers.

## Minimal Temporal history

The referral workflow stores only:

- referral ID;
- dispatch ID;
- response due timestamp, when one exists;
- initiating actor ID;
- provider status signal values.

Authorized household data remains in the existing referral dispatch record and is loaded worker-side by the dispatch activity. It is not copied into Temporal workflow history.

## External dispatch configuration

The Provider worker reads a secret runtime setting named `HAMOON_PROVIDER_DISPATCH_CONFIG`. The value is a JSON object keyed by Provider UUID:

```json
{
  "11111111-1111-1111-1111-111111111111": {
    "endpoint": "https://provider.example/referrals",
    "bearer_token": "<secret injected by the deployment secret manager>"
  }
}
```

Rules:

- endpoint must be remote HTTPS;
- credentials in URL are rejected;
- bearer tokens are held in the secret runtime configuration, never Provider Registry rows;
- redirects are not followed, preventing credentials from being forwarded to another origin;
- Production provider-worker startup fails fast when the dispatch configuration is absent or invalid.

## Idempotency and retry

Every outbound request carries:

- the original `Idempotency-Key`;
- `X-Hamoon-Dispatch-Id`;
- `X-Hamoon-Referral-Id`.

Temporal retries transport failures and HTTP 5xx responses without an attempt cap; retry state stays inside Temporal rather than being duplicated in a second database retry engine. HTTP 4xx responses are treated as permanent delivery failures and the dispatch is marked `FAILED`. Only a 2xx response may mark a dispatch `SENT`.

`response_due_at` governs the provider-response wait after delivery. If delivery was delayed and the absolute due time has already passed, the workflow immediately executes the guarded `NO_RESPONSE` check after successful delivery.

The provider-worker also reconciles persisted `PENDING` dispatches, so a temporary failure to start the workflow from the API request does not lose authorized work.

## Callback and timeout behavior

Provider callback endpoints retain the existing OIDC Provider Identity boundary and provider scoping. After the callback transaction commits, Hamoon signals the dispatch-scoped workflow.

If `response_due_at` exists and no provider response has arrived by that time, the workflow executes a system transition to `NO_RESPONSE` and atomically materializes an assigned `REFERRAL_FOLLOWUP` work item for the caseworker queue. The activity re-reads the referral first; if the database already shows a provider response or cancellation, it does not create a false timeout. Activity retries reuse an existing referral follow-up item instead of duplicating it.

Caseworker cancellation signals the workflow and stops the waiting path.

## Operational boundary

`provider-worker` is a separately runnable process and has its own exact-release heartbeat. Stage Admission requires it to run from the exact promoted backend image and requires a healthy heartbeat.

Repository and Stage tests prove the adapter/orchestration contract. They do not prove that any external provider is reachable or has accepted a real referral. That claim requires environment-specific provider sandbox or Production evidence.
