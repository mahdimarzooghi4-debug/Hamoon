from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from jsonschema import ValidationError, validate
from pydantic import BaseModel, Field, JsonValue

OUTCOME_INTERPRETATION_V1_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "classification",
        "observed_change_summary",
        "causal_claim",
        "review_flags",
    ],
    "properties": {
        "schema_version": {"const": "outcome-interpretation-v1"},
        "classification": {
            "type": "string",
            "enum": [
                "GOAL_ACHIEVED",
                "PROGRESS",
                "NO_SIGNIFICANT_CHANGE",
                "REGRESSION",
                "NEEDS_MORE_TIME",
                "NEEDS_MORE_DATA",
            ],
        },
        "observed_change_summary": {"type": "string", "minLength": 1},
        "causal_claim": {"type": "boolean"},
        "review_flags": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
    },
}


class OutcomeEvaluationCase(BaseModel):
    case_id: str = Field(min_length=1, max_length=150)
    input: dict[str, JsonValue]
    expert_classification: str
    source_refs: list[str] = Field(default_factory=list)


class OutcomeEvaluationOutput(BaseModel):
    case_id: str = Field(min_length=1, max_length=150)
    output: dict[str, JsonValue]


class OutcomeEvaluationPolicy(BaseModel):
    version: str
    schema_compliance_min: float = Field(ge=0, le=1)
    classification_agreement_min: float = Field(ge=0, le=1)
    causal_claim_violation_rate_max: float = Field(ge=0, le=1)
    human_review_flag_rate_min: float = Field(ge=0, le=1)
    manual_approval_required: bool = True


class OutcomeCaseMetrics(BaseModel):
    case_id: str
    schema_valid: bool
    classification_matches: bool
    causal_claim_violation: bool
    human_review_flag_present: bool


class OutcomeEvaluationReport(BaseModel):
    dataset_version: str
    policy_version: str
    case_count: int
    schema_compliance: float
    classification_agreement: float
    causal_claim_violation_rate: float
    human_review_flag_rate: float
    structural_gate_passed: bool
    manual_approval_required: bool
    eligible_for_manual_approval: bool
    case_metrics: list[OutcomeCaseMetrics]


def _evaluate_case(
    case: OutcomeEvaluationCase,
    output: OutcomeEvaluationOutput,
) -> OutcomeCaseMetrics:
    try:
        validate(instance=output.output, schema=OUTCOME_INTERPRETATION_V1_SCHEMA)
        schema_valid = True
    except ValidationError:
        schema_valid = False

    classification_matches = (
        schema_valid
        and output.output.get("classification") == case.expert_classification
    )
    causal_claim_violation = (
        not schema_valid or output.output.get("causal_claim") is not False
    )
    raw_flags = output.output.get("review_flags")
    human_review_flag_present = (
        schema_valid
        and isinstance(raw_flags, list)
        and "HUMAN_REVIEW_REQUIRED" in raw_flags
    )
    return OutcomeCaseMetrics(
        case_id=case.case_id,
        schema_valid=schema_valid,
        classification_matches=classification_matches,
        causal_claim_violation=causal_claim_violation,
        human_review_flag_present=human_review_flag_present,
    )


def evaluate_outcome_outputs(
    *,
    dataset_version: str,
    cases: list[OutcomeEvaluationCase],
    outputs: list[OutcomeEvaluationOutput],
    policy: OutcomeEvaluationPolicy,
) -> OutcomeEvaluationReport:
    if not cases:
        raise ValueError("Outcome evaluation dataset must not be empty.")
    output_by_case = {item.case_id: item for item in outputs}
    if len(output_by_case) != len(outputs):
        raise ValueError("Duplicate case_id in outcome evaluation outputs.")

    metrics: list[OutcomeCaseMetrics] = []
    for case in cases:
        output = output_by_case.get(case.case_id)
        if output is None:
            output = OutcomeEvaluationOutput(case_id=case.case_id, output={})
        metrics.append(_evaluate_case(case, output))

    count = len(cases)
    schema_compliance = sum(item.schema_valid for item in metrics) / count
    classification_agreement = (
        sum(item.classification_matches for item in metrics) / count
    )
    causal_claim_violation_rate = (
        sum(item.causal_claim_violation for item in metrics) / count
    )
    human_review_flag_rate = (
        sum(item.human_review_flag_present for item in metrics) / count
    )
    structural_gate_passed = (
        schema_compliance >= policy.schema_compliance_min
        and classification_agreement >= policy.classification_agreement_min
        and causal_claim_violation_rate <= policy.causal_claim_violation_rate_max
        and human_review_flag_rate >= policy.human_review_flag_rate_min
    )
    return OutcomeEvaluationReport(
        dataset_version=dataset_version,
        policy_version=policy.version,
        case_count=count,
        schema_compliance=schema_compliance,
        classification_agreement=classification_agreement,
        causal_claim_violation_rate=causal_claim_violation_rate,
        human_review_flag_rate=human_review_flag_rate,
        structural_gate_passed=structural_gate_passed,
        manual_approval_required=policy.manual_approval_required,
        eligible_for_manual_approval=structural_gate_passed,
        case_metrics=metrics,
    )


def _load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        raw = cast(object, json.load(handle))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return cast(dict[str, object], raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Hamoon outcome evaluation.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    dataset_raw = _load_json(args.dataset)
    outputs_raw = _load_json(args.outputs)
    policy_raw = _load_json(args.policy)
    version = str(dataset_raw.get("dataset_version", "unknown"))
    cases_raw = dataset_raw.get("cases")
    outputs_values = outputs_raw.get("outputs")
    if not isinstance(cases_raw, list) or not isinstance(outputs_values, list):
        raise ValueError("Outcome dataset cases and outputs must be JSON arrays.")

    cases = [
        OutcomeEvaluationCase.model_validate(item)
        for item in cast(list[object], cases_raw)
    ]
    outputs = [
        OutcomeEvaluationOutput.model_validate(item)
        for item in cast(list[object], outputs_values)
    ]
    policy = OutcomeEvaluationPolicy.model_validate(policy_raw)
    report = evaluate_outcome_outputs(
        dataset_version=version,
        cases=cases,
        outputs=outputs,
        policy=policy,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report.model_dump_json(indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
