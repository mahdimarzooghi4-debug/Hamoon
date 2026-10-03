import pytest
from jsonschema import ValidationError, validate

from hamoon.infrastructure.ai.outcome_runtime import OUTCOME_INTERPRETATION_V1_SCHEMA


def _valid_outcome() -> dict:
    return {
        "schema_version": "outcome-interpretation-v1",
        "classification": "PROGRESS",
        "observed_change_summary": "Observed change only.",
        "causal_claim": False,
        "supporting_feature_refs": ["delta.e"],
        "review_flags": ["HUMAN_REVIEW_REQUIRED"],
    }


def test_outcome_contract_requires_non_causal_human_review_output() -> None:
    validate(instance=_valid_outcome(), schema=OUTCOME_INTERPRETATION_V1_SCHEMA)

    causal = _valid_outcome()
    causal["causal_claim"] = True
    with pytest.raises(ValidationError):
        validate(instance=causal, schema=OUTCOME_INTERPRETATION_V1_SCHEMA)

    autonomous = _valid_outcome()
    autonomous["review_flags"] = []
    with pytest.raises(ValidationError):
        validate(instance=autonomous, schema=OUTCOME_INTERPRETATION_V1_SCHEMA)
