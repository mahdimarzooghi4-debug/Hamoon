# Hamoon — Decision Trace Contract

Status: PB-083 is implemented as an auditable, version-bound trace across the AI-assisted decision chain.

## Trace identity

Every AI decision trace records:

- household ID;
- trace type;
- Accepted State context version captured before inference;
- state/feature fingerprint;
- official PGOR snapshot ID;
- feature package ID;
- AI decision ID;
- human decision ID, when reviewed;
- prescription ID, when applicable;
- intervention ID, when activated;
- referral ID, when applicable;
- provider result ID, when applicable;
- outcome ID, when applicable;
- learning signal ID, when created;
- opened and closed timestamps.

The trace does not infer or reconstruct missing links from free text.

## Accepted State stale-safety

Diagnosis, prescription and outcome interpretation generation capture the authoritative Accepted State `context_version` before the external AI call.

Immediately before persistence, Hamoon reads the context version again. If it changed during inference, persistence fails with:

```text
409 HOUSEHOLD_CONTEXT_VERSION_CONFLICT
```

The AI output is not promoted into an AIDecision or DecisionTrace in that stale transaction.

This is the same safety principle used by Provider Matching: a model result is valid only for the state context it was generated against.

## Human review and learning signal linkage

When a diagnosis, prescription or AI-assisted outcome is reviewed, the DecisionTrace is updated in the same database transaction with the resulting HumanDecision and LearningSignal identifiers.

A trace may remain open for a deferred human decision, but the learning signal produced by that review is still linked to the trace.

## API read model

`GET /api/v1/ai/decisions/{decision_id}/trace` exposes the trace linkage fields to an authorized caseworker after household assignment enforcement.

This read model is for auditability and reproducibility. It does not authorize downstream actions and it does not change the human-review gates.
