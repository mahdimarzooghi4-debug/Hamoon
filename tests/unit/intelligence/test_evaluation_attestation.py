from hamoon.domains.intelligence.application.evaluation_governance import (
    attest_evaluation_report,
)
from hamoon.infrastructure.ai.contracts import AITaskClass


def _outcome_report() -> dict:
    return {
        "dataset_version": "outcome-v1",
        "policy_version": "outcome-eval-v1",
        "schema_compliance": 1.0,
        "classification_agreement": 1.0,
        "causal_claim_violation_rate": 0.0,
        "human_review_flag_rate": 1.0,
        "grounding_coverage": 1.0,
        "unsupported_ref_rate": 0.0,
        "structural_gate_passed": True,
        "manual_approval_required": True,
        "eligible_for_manual_approval": True,
    }


def test_outcome_report_attestation_derives_pass_and_stable_digest() -> None:
    report = _outcome_report()
    first = attest_evaluation_report(
        task_class=AITaskClass.OUTCOME_INTERPRETATION,
        expected_policy_version="outcome-eval-v1",
        report=report,
    )
    reordered = dict(reversed(list(report.items())))
    second = attest_evaluation_report(
        task_class=AITaskClass.OUTCOME_INTERPRETATION,
        expected_policy_version="outcome-eval-v1",
        report=reordered,
    )

    assert first.passed is True
    assert len(first.report_digest) == 64
    assert first.report_digest == second.report_digest


def test_failed_structural_gate_is_recorded_as_failed_not_promotable() -> None:
    report = _outcome_report()
    report["structural_gate_passed"] = False
    report["eligible_for_manual_approval"] = False
    report["classification_agreement"] = 0.4

    attestation = attest_evaluation_report(
        task_class=AITaskClass.OUTCOME_INTERPRETATION,
        expected_policy_version="outcome-eval-v1",
        report=report,
    )

    assert attestation.passed is False


def test_outcome_attestation_rejects_safety_bypass() -> None:
    report = _outcome_report()
    report["unsupported_ref_rate"] = 0.2

    try:
        attest_evaluation_report(
            task_class=AITaskClass.OUTCOME_INTERPRETATION,
            expected_policy_version="outcome-eval-v1",
            report=report,
        )
    except ValueError as exc:
        assert str(exc) == "EVALUATION_OUTCOME_UNSUPPORTED_REF_FAILED"
    else:
        raise AssertionError("unsupported refs must block a passing attestation")


def test_attestation_rejects_policy_mismatch() -> None:
    try:
        attest_evaluation_report(
            task_class=AITaskClass.OUTCOME_INTERPRETATION,
            expected_policy_version="outcome-eval-v2",
            report=_outcome_report(),
        )
    except ValueError as exc:
        assert str(exc) == "EVALUATION_REPORT_POLICY_MISMATCH"
    else:
        raise AssertionError("policy mismatch must be rejected")


def test_attestation_requires_explicit_manual_approval_boundary() -> None:
    report = _outcome_report()
    report["manual_approval_required"] = False

    try:
        attest_evaluation_report(
            task_class=AITaskClass.OUTCOME_INTERPRETATION,
            expected_policy_version="outcome-eval-v1",
            report=report,
        )
    except ValueError as exc:
        assert str(exc) == "EVALUATION_REPORT_MANUAL_APPROVAL_REQUIRED"
    else:
        raise AssertionError("manual approval boundary must remain explicit")
