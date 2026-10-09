# Hamoon Foundation Behavior Dataset v1

Status: **DRAFT SOURCE ONLY — NOT APPROVED FOR TRAINING**

This directory records the first day-one supervised behavior source pack for Hamoon.

It teaches **observable decision discipline**, not household facts and not hidden chain-of-thought. Natural-language target fields are Persian; canonical schema keys and feature references remain unchanged.

## What v1 teaches

- use only supplied versioned features;
- never calculate, correct, or replace authoritative PGOR values;
- preserve unknowns instead of guessing;
- do not invent thresholds;
- ground claims in explicit feature keys;
- keep Provider Result separate from Hamoon Outcome;
- keep `causal_claim=false`;
- produce a proposal for mandatory Human Review;
- do not select providers, activate interventions, dispatch referrals, or make final human decisions.

## Included task sources

- `DIAGNOSIS`: 12 synthetic supervised examples aligned to `diagnosis-input-v1` and `diagnosis-v1`.
- `OUTCOME_INTERPRETATION`: 12 synthetic supervised examples aligned to the current outcome feature/output contracts.

No production household data is present.

## Why Prescription is not in v1

The current Prescription target schema requires `review_schedule` and `success_criteria`. A day-one synthetic pack would have to invent policy-bearing values for those fields. That would violate Hamoon's no-invention rule, so Prescription foundation examples are explicitly deferred until there is a reviewed authoritative source.

## Governance boundary

These files are **not** a `LearningDatasetVersion(APPROVED)` and are not automatically consumable by the Internal Training Control Plane.

The current database learning dataset model is provenance-bound to curated `LearningSignal` records. Do **not** fabricate signal IDs to import this source pack.

A future controlled import must:
1. preserve explicit provenance for synthetic foundation examples;
2. require Human Review / approval;
3. create task-specific versioned datasets;
4. keep training and evaluation examples independent;
5. never auto-promote a model or routing policy.

Repository commit history is the source version history for this draft source pack.

See `manifest.json` and `behavior_contract.json`.
