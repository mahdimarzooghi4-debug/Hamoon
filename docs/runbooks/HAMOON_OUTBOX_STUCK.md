# HAMOON_OUTBOX_STUCK

## Signal

The durable outbox exceeds 100 pending messages and the oldest message is older than five minutes for ten minutes.

## Diagnosis

Check exact-release Outbox worker heartbeat, NATS reachability, publish failures, retry timing, and the oldest unpublished event metadata. Do not inspect sensitive event payloads.

## Immediate actions

Restore NATS or worker service first. Do not delete or mark events published manually to make the alert disappear.

## Escalation

Escalate when backlog age keeps growing, publish failures repeat, or downstream workflows depend on delayed events.

## Safe recovery

Allow the durable worker to drain naturally, verify pending count and oldest age return to normal, and confirm event identity remains intact.
