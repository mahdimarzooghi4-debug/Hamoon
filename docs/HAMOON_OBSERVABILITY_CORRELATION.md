# Hamoon — Observability Correlation Contract

Status: PB-120 is implemented and CI-enforced.

Hamoon keeps two complementary correlation mechanisms:

- W3C trace context for OpenTelemetry spans and outbound instrumented HTTP calls.
- A stable Hamoon business `correlation_id` that survives durable events and long-running workflows.

## Request boundary

Inbound API requests receive or generate:

```text
X-Request-Id
X-Correlation-Id
```

The values are stored in request context and returned on the response.

## Event / NATS boundary

Domain event recording injects the active W3C `traceparent` / `tracestate` into the durable Domain Event and Outbox row.

The NATS envelope and headers preserve:

```text
correlation_id
traceparent
tracestate
```

This allows asynchronous event delivery to retain both business and distributed-trace identity.

## Temporal boundary

Referral and Reassessment workflow inputs carry an explicit `correlation_id`.

When a workflow is started from an API request, the active request correlation is used. When reconciliation starts or restores a workflow outside a request context, the deterministic workflow ID is used as the correlation fallback.

All downstream Temporal activity inputs use the workflow input correlation rather than replacing it with the Temporal workflow ID. This preserves the originating business-flow correlation across long-running timers, signals and retries.

## AI boundary

The provider-neutral AI Gateway creates a custom span:

```text
hamoon.ai.generate_structured
```

with PII-safe attributes:

```text
hamoon.correlation_id
hamoon.ai.task_class
hamoon.ai.provider
hamoon.ai.model_alias
hamoon.ai.routing_policy_version
hamoon.ai.prompt_policy_version
hamoon.ai.output_schema_version
hamoon.ai.feature_schema_version
hamoon.ai.status
```

No raw feature payload, prompt, response, household identifier, token or evidence text is attached to the span.

## CI contract

CI explicitly verifies:

- Referral workflow input correlation.
- Reassessment workflow input correlation and deterministic reconciliation fallback.
- AI span correlation and bounded trace attributes.

Structured-log redaction, Stage OTLP transport and external telemetry verification remain covered by their dedicated gates.
