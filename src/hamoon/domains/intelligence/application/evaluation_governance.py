from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from pydantic import JsonValue

from hamoon.infrastructure.ai.contracts import AITaskClass


@dataclass(frozen=True, slots=True)
class EvaluationReportAttestation:
    passed: bool
    report_digest: str
    summary_metrics: dict[str, JsonValue]


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _number(report: dict[str, JsonValue], key: str) -> float:
    value = report.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"EVALUATION_REPORT_METRIC_INVALID:{key}")
    return float(value)


def require_independent_evaluation_dataset(
    *,
    training_dataset_version_id: UUID,
    training_dataset_manifest_digest: str,
    evaluation_dataset_version_id: UUID,
    evaluation_dataset_manifest_digest: str,
) -> None:
    if evaluation_dataset_version_id == training_dataset_version_id:
        raise ValueError("EVALUATION_DATASET_REUSES_TRAINING_VERSION")
    if evaluation_dataset_manifest_digest == training_dataset_manifest_digest:
        raise ValueError("EVALUATION_DATASET_REUSES_TRAINING_MANIFEST")


def attest_evaluation_report(
    *,
    task_class: AITaskClass,
    expected_policy_version: str,
    expected_dataset_version: str,
    report: dict[str, JsonValue],
) -> EvaluationReportAttestation:
    if report.get("policy_version") != expected_policy_version:
        raise ValueError("EVALUATION_REPORT_POLICY_MISMATCH")
    if report.get("dataset_version") != expected_dataset_version:
        raise ValueError("EVALUATION_REPORT_DATASET_MISMATCH")

    structural_gate = report.get("structural_gate_passed")
    if not isinstance(structural_gate, bool):
        raise ValueError("EVALUATION_REPORT_STRUCTURAL_GATE_REQUIRED")
    if report.get("manual_approval_required") is not True:
        raise ValueError("EVALUATION_REPORT_MANUAL_APPROVAL_REQUIRED")
    eligible = report.get("eligible_for_manual_approval")
    if not isinstance(eligible, bool) or eligible is not structural_gate:
        raise ValueError("EVALUATION_REPORT_ELIGIBILITY_INVALID")

    if structural_gate and task_class is AITaskClass.OUTCOME_INTERPRETATION:
        if _number(report, "causal_claim_violation_rate") != 0.0:
            raise ValueError("EVALUATION_OUTCOME_CAUSAL_SAFETY_FAILED")
        if _number(report, "human_review_flag_rate") != 1.0:
            raise ValueError("EVALUATION_OUTCOME_HUMAN_REVIEW_FAILED")
        if _number(report, "grounding_coverage") != 1.0:
            raise ValueError("EVALUATION_OUTCOME_GROUNDING_FAILED")
        if _number(report, "unsupported_ref_rate") != 0.0:
            raise ValueError("EVALUATION_OUTCOME_UNSUPPORTED_REF_FAILED")

    if structural_gate and task_class is AITaskClass.DIAGNOSIS:
        if _number(report, "evidence_coverage") != 1.0:
            raise ValueError("EVALUATION_DIAGNOSIS_GROUNDING_FAILED")
        if _number(report, "unsupported_claim_rate") != 0.0:
            raise ValueError("EVALUATION_DIAGNOSIS_UNSUPPORTED_CLAIM_FAILED")
        if _number(report, "safety_violation_rate") != 0.0:
            raise ValueError("EVALUATION_DIAGNOSIS_SAFETY_FAILED")

    summary_metrics = dict(report)
    return EvaluationReportAttestation(
        passed=structural_gate,
        report_digest=_canonical_digest(summary_metrics),
        summary_metrics=summary_metrics,
    )
