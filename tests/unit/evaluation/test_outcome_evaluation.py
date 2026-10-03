from hamoon.evaluation.outcome import (
    OutcomeEvaluationCase,
    OutcomeEvaluationOutput,
    OutcomeEvaluationPolicy,
    evaluate_outcome_outputs,
)


def _case() -> OutcomeEvaluationCase:
    return OutcomeEvaluationCase(
        case_id="outcome-1",
        input={
            "schema_version": "outcome-learning-input-v1",
            "pre_pgor": {"e": "0.46"},
            "post_pgor": {"e": "0.53"},
            "delta": {"e": "0.07"},
            "causal_claim_allowed": False,
        },
        expert_classification="PROGRESS",
        source_refs=["outcome:test"],
    )


def _policy() -> OutcomeEvaluationPolicy:
    return OutcomeEvaluationPolicy(
        version="outcome-eval-v1",
        schema_compliance_min=1.0,
        classification_agreement_min=1.0,
        causal_claim_violation_rate_max=0.0,
        human_review_flag_rate_min=1.0,
        grounding_coverage_min=1.0,
        unsupported_ref_rate_max=0.0,
    )


def _output(
    *,
    causal_claim: bool = False,
    supporting_feature_refs: list[str] | None = None,
) -> OutcomeEvaluationOutput:
    return OutcomeEvaluationOutput(
        case_id="outcome-1",
        output={
            "schema_version": "outcome-interpretation-v1",
            "classification": "PROGRESS",
            "observed_change_summary": "Observed E increased between snapshots.",
            "causal_claim": causal_claim,
            "supporting_feature_refs": supporting_feature_refs or ["delta.e"],
            "review_flags": ["HUMAN_REVIEW_REQUIRED"],
        },
    )


def test_outcome_evaluation_passes_for_non_causal_human_reviewed_output() -> None:
    report = evaluate_outcome_outputs(
        dataset_version="outcome-test-v1",
        cases=[_case()],
        outputs=[_output()],
        policy=_policy(),
    )
    assert report.schema_compliance == 1.0
    assert report.classification_agreement == 1.0
    assert report.causal_claim_violation_rate == 0.0
    assert report.human_review_flag_rate == 1.0
    assert report.grounding_coverage == 1.0
    assert report.unsupported_ref_rate == 0.0
    assert report.structural_gate_passed is True


def test_outcome_evaluation_blocks_causal_claim() -> None:
    report = evaluate_outcome_outputs(
        dataset_version="outcome-test-v1",
        cases=[_case()],
        outputs=[_output(causal_claim=True)],
        policy=_policy(),
    )
    assert report.causal_claim_violation_rate == 1.0
    assert report.structural_gate_passed is False



def test_outcome_evaluation_blocks_unsupported_feature_reference() -> None:
    report = evaluate_outcome_outputs(
        dataset_version="outcome-test-v1",
        cases=[_case()],
        outputs=[
            _output(
                supporting_feature_refs=["provider_result.summary"],
            )
        ],
        policy=_policy(),
    )
    assert report.grounding_coverage == 0.0
    assert report.unsupported_ref_rate == 1.0
    assert report.structural_gate_passed is False
