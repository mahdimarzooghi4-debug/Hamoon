# HAMOON_ALERT_DELIVERY_PROBE

## Signal

A synthetic critical alert created by the controlled External Alert Delivery
Verification workflow is firing through the configured Production Alertmanager route.

## Diagnosis

Confirm the alert carries the expected `hamoon_probe_id`, routes to the intended
receiver, and is associated with the exact Production-monitored commit. It must not
contain household or other business data.

## Immediate actions

No business-system remediation is required. Acknowledge the notification only as a
delivery test and allow the verification workflow to resolve the synthetic alert.

## Escalation

Escalate to Production Ops when the probe does not reach the configured receiver,
receiver-labelled Alertmanager metrics are unavailable, or notification failures
increase during the probe.

## Safe recovery

Restore Alertmanager routing or receiver connectivity without weakening authentication.
Re-run the verification after recovery. Never disable alerts or bypass the monitored
Production evidence chain to make the test pass.
