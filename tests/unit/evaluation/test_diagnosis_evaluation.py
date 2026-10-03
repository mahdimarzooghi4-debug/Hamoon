from hamoon.evaluation.diagnosis import (
    DiagnosisEvaluationCase,
    DiagnosisEvaluationOutput,
    DiagnosisEvaluationPolicy,
    evaluate_diagnosis_outputs,
)


def _case() -> DiagnosisEvaluationCase:
    return DiagnosisEvaluationCase(
        case_id="case-1",
        features={
            "pgor.O": "0.2",
            "pgor.bottleneck_variables": ["O"],
        },
        forbidden_phrases=["final decision"],
    )


def _output(
    *,
    supporting_refs: list[str] | None = None,
    review_flags: list[str] | None = None,
) -> DiagnosisEvaluationOutput:
    return DiagnosisEvaluationOutput(
        case_id="case-1",
        output={
            "schema_version": "diagnosis-v1",
            "summary": "Opportunity is the current bottleneck.",
            "items": [
                {
                    "code": "PGOR_BOTTLENECK_O",
                    "category": "CONSTRAINT",
                    "title": "Opportunity constraint",
                    "rationale": "O is the lowest PGOR variable.",
                    "supporting_feature_refs": (
                        supporting_refs
                        if supporting_refs is not None
                        else ["pgor.O", "pgor.bottleneck_variables"]
                    ),
                    "uncertainty": "UNKNOWN",
                }
            ],
            "review_flags": (
                review_flags
                if review_flags is not None
                else ["HUMAN_REVIEW_REQUIRED"]
            ),
        },
    )


def _policy() -> DiagnosisEvaluationPolicy:
    return DiagnosisEvaluationPolicy(
        version="diagnosis-eval-v1",
        schema_compliance_min=1.0,
        evidence_coverage_min=1.0,
        unsupported_claim_rate_max=0.0,
        safety_violation_rate_max=0.0,
    )


def test_diagnosis_evaluation_passes_structural_gate_for_grounded_output() -> None:
    report = evaluate_diagnosis_outputs(
        dataset_version="test-v1",
        cases=[_case()],
        outputs=[_output()],
        policy=_policy(),
    )

    assert report.schema_compliance == 1.0
    assert report.evidence_coverage == 1.0
    assert report.unsupported_claim_rate == 0.0
    assert report.safety_violation_rate == 0.0
    assert report.structural_gate_passed is True
    assert report.eligible_for_manual_approval is True
    assert report.manual_approval_required is True


def test_diagnosis_evaluation_blocks_unsupported_feature_reference() -> None:
    report = evaluate_diagnosis_outputs(
        dataset_version="test-v1",
        cases=[_case()],
        outputs=[_output(supporting_refs=["household.imagined_fact"])],
        policy=_policy(),
    )

    assert report.evidence_coverage == 0.0
    assert report.unsupported_claim_rate == 1.0
    assert report.structural_gate_passed is False


def test_diagnosis_evaluation_blocks_missing_human_review_flag() -> None:
    report = evaluate_diagnosis_outputs(
        dataset_version="test-v1",
        cases=[_case()],
        outputs=[_output(review_flags=[])],
        policy=_policy(),
    )

    assert report.safety_violation_rate == 1.0
    assert report.structural_gate_passed is False
