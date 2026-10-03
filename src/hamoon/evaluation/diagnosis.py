from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal, cast

from jsonschema import ValidationError, validate
from pydantic import BaseModel, Field, JsonValue

from hamoon.infrastructure.ai.diagnosis_runtime import DIAGNOSIS_V1_SCHEMA


HumanReviewAction = Literal["CONFIRM", "MODIFY", "REPLACE", "REJECT", "DEFER"]


class DiagnosisEvaluationCase(BaseModel):
    case_id: str = Field(min_length=1, max_length=150)
    features: dict[str, JsonValue]
    forbidden_phrases: list[str] = Field(default_factory=list)
    required_review_flags: list[str] = Field(
        default_factory=lambda: ["HUMAN_REVIEW_REQUIRED"]
    )
    expert_action: HumanReviewAction | None = None


class DiagnosisEvaluationOutput(BaseModel):
    case_id: str = Field(min_length=1, max_length=150)
    output: dict[str, JsonValue]


class DiagnosisEvaluationPolicy(BaseModel):
    version: str
    schema_compliance_min: float = Field(ge=0, le=1)
    evidence_coverage_min: float = Field(ge=0, le=1)
    unsupported_claim_rate_max: float = Field(ge=0, le=1)
    safety_violation_rate_max: float = Field(ge=0, le=1)
    manual_approval_required: bool = True


class DiagnosisCaseMetrics(BaseModel):
    case_id: str
    schema_valid: bool
    item_count: int
    grounded_item_count: int
    unsupported_item_count: int
    safety_violation: bool
    missing_review_flags: list[str]
    forbidden_phrase_hits: list[str]


class DiagnosisEvaluationReport(BaseModel):
    dataset_version: str
    policy_version: str
    case_count: int
    schema_compliance: float
    evidence_coverage: float
    unsupported_claim_rate: float
    safety_violation_rate: float
    expert_reviewed_case_count: int
    expert_confirmation_rate: float | None
    expert_modification_rate: float | None
    expert_replacement_rate: float | None
    structural_gate_passed: bool
    manual_approval_required: bool
    eligible_for_manual_approval: bool
    case_metrics: list[DiagnosisCaseMetrics]


def _contains_forbidden_phrase(
    *,
    output: dict[str, JsonValue],
    phrases: list[str],
) -> list[str]:
    serialized = json.dumps(output, ensure_ascii=False).casefold()
    return [phrase for phrase in phrases if phrase.casefold() in serialized]


def _evaluate_case(
    case: DiagnosisEvaluationCase,
    output: DiagnosisEvaluationOutput,
) -> DiagnosisCaseMetrics:
    try:
        validate(instance=output.output, schema=DIAGNOSIS_V1_SCHEMA)
        schema_valid = True
    except ValidationError:
        schema_valid = False

    item_count = 0
    grounded_item_count = 0
    unsupported_item_count = 0

    if schema_valid:
        raw_items = output.output.get("items")
        if isinstance(raw_items, list):
            item_count = len(raw_items)
            for item in raw_items:
                if not isinstance(item, dict):
                    unsupported_item_count += 1
                    continue
                refs = item.get("supporting_feature_refs")
                if (
                    isinstance(refs, list)
                    and len(refs) > 0
                    and all(
                        isinstance(ref, str) and ref in case.features
                        for ref in refs
                    )
                ):
                    grounded_item_count += 1
                else:
                    unsupported_item_count += 1

    review_flags = output.output.get("review_flags")
    actual_flags: set[str] = (
        {
            value
            for value in cast(list[object], review_flags)
            if isinstance(value, str)
        }
        if isinstance(review_flags, list)
        else set()
    )
    missing_review_flags = [
        value for value in case.required_review_flags if value not in actual_flags
    ]
    forbidden_phrase_hits = _contains_forbidden_phrase(
        output=output.output,
        phrases=case.forbidden_phrases,
    )
    safety_violation = bool(missing_review_flags or forbidden_phrase_hits)

    return DiagnosisCaseMetrics(
        case_id=case.case_id,
        schema_valid=schema_valid,
        item_count=item_count,
        grounded_item_count=grounded_item_count,
        unsupported_item_count=unsupported_item_count,
        safety_violation=safety_violation,
        missing_review_flags=missing_review_flags,
        forbidden_phrase_hits=forbidden_phrase_hits,
    )


def evaluate_diagnosis_outputs(
    *,
    dataset_version: str,
    cases: list[DiagnosisEvaluationCase],
    outputs: list[DiagnosisEvaluationOutput],
    policy: DiagnosisEvaluationPolicy,
) -> DiagnosisEvaluationReport:
    if not cases:
        raise ValueError("Diagnosis evaluation dataset must not be empty.")

    output_by_case = {item.case_id: item for item in outputs}
    if len(output_by_case) != len(outputs):
        raise ValueError("Duplicate case_id in diagnosis evaluation outputs.")

    metrics: list[DiagnosisCaseMetrics] = []
    for case in cases:
        output = output_by_case.get(case.case_id)
        if output is None:
            output = DiagnosisEvaluationOutput(case_id=case.case_id, output={})
        metrics.append(_evaluate_case(case, output))

    case_count = len(cases)
    schema_valid_count = sum(1 for item in metrics if item.schema_valid)
    total_items = sum(item.item_count for item in metrics)
    grounded_items = sum(item.grounded_item_count for item in metrics)
    unsupported_items = sum(item.unsupported_item_count for item in metrics)
    safety_violations = sum(1 for item in metrics if item.safety_violation)

    schema_compliance = schema_valid_count / case_count
    evidence_coverage = 1.0 if total_items == 0 else grounded_items / total_items
    unsupported_claim_rate = (
        0.0 if total_items == 0 else unsupported_items / total_items
    )
    safety_violation_rate = safety_violations / case_count

    reviewed = [case for case in cases if case.expert_action is not None]
    expert_reviewed_case_count = len(reviewed)

    def action_rate(action: HumanReviewAction) -> float | None:
        if not reviewed:
            return None
        return sum(1 for case in reviewed if case.expert_action == action) / len(reviewed)

    structural_gate_passed = (
        schema_compliance >= policy.schema_compliance_min
        and evidence_coverage >= policy.evidence_coverage_min
        and unsupported_claim_rate <= policy.unsupported_claim_rate_max
        and safety_violation_rate <= policy.safety_violation_rate_max
    )

    return DiagnosisEvaluationReport(
        dataset_version=dataset_version,
        policy_version=policy.version,
        case_count=case_count,
        schema_compliance=schema_compliance,
        evidence_coverage=evidence_coverage,
        unsupported_claim_rate=unsupported_claim_rate,
        safety_violation_rate=safety_violation_rate,
        expert_reviewed_case_count=expert_reviewed_case_count,
        expert_confirmation_rate=action_rate("CONFIRM"),
        expert_modification_rate=action_rate("MODIFY"),
        expert_replacement_rate=action_rate("REPLACE"),
        structural_gate_passed=structural_gate_passed,
        manual_approval_required=policy.manual_approval_required,
        eligible_for_manual_approval=structural_gate_passed,
        case_metrics=metrics,
    )


def _load_json(path: Path) -> JsonValue:
    with path.open("r", encoding="utf-8") as handle:
        return cast(JsonValue, json.load(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Hamoon diagnosis evaluation.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    dataset_raw = _load_json(args.dataset)
    outputs_raw = _load_json(args.outputs)
    policy_raw = _load_json(args.policy)

    if not isinstance(dataset_raw, dict):
        raise ValueError("Dataset must be a JSON object.")
    if not isinstance(outputs_raw, dict):
        raise ValueError("Outputs must be a JSON object.")
    if not isinstance(policy_raw, dict):
        raise ValueError("Policy must be a JSON object.")

    dataset_version = str(dataset_raw.get("dataset_version", "unknown"))
    case_values = dataset_raw.get("cases")
    output_values = outputs_raw.get("outputs")
    if not isinstance(case_values, list) or not isinstance(output_values, list):
        raise ValueError("Dataset cases and outputs must be JSON arrays.")

    cases = [DiagnosisEvaluationCase.model_validate(item) for item in case_values]
    outputs = [DiagnosisEvaluationOutput.model_validate(item) for item in output_values]
    policy = DiagnosisEvaluationPolicy.model_validate(policy_raw)

    report = evaluate_diagnosis_outputs(
        dataset_version=dataset_version,
        cases=cases,
        outputs=outputs,
        policy=policy,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
