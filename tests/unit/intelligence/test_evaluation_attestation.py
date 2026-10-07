from uuid import UUID

from hamoon.domains.intelligence.application.evaluation_governance import (
    attest_evaluation_report,
    require_independent_evaluation_dataset,
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



def test_evaluation_dataset_must_not_reuse_training_version() -> None:
    training_id = UUID("11111111-1111-1111-1111-111111111111")

    try:
        require_independent_evaluation_dataset(
            training_dataset_version_id=training_id,
            training_dataset_manifest_digest="a" * 64,
            evaluation_dataset_version_id=training_id,
            evaluation_dataset_manifest_digest="b" * 64,
        )
    except ValueError as exc:
        assert str(exc) == "EVALUATION_DATASET_REUSES_TRAINING_VERSION"
    else:
        raise AssertionError("evaluation must not reuse the training dataset version")


def test_evaluation_dataset_must_not_reuse_training_manifest() -> None:
    try:
        require_independent_evaluation_dataset(
            training_dataset_version_id=UUID(
                "11111111-1111-1111-1111-111111111111"
            ),
            training_dataset_manifest_digest="a" * 64,
            evaluation_dataset_version_id=UUID(
                "22222222-2222-2222-2222-222222222222"
            ),
            evaluation_dataset_manifest_digest="a" * 64,
        )
    except ValueError as exc:
        assert str(exc) == "EVALUATION_DATASET_REUSES_TRAINING_MANIFEST"
    else:
        raise AssertionError("evaluation must use independent dataset content")


def test_evaluation_dataset_accepts_independent_version_and_manifest() -> None:
    require_independent_evaluation_dataset(
        training_dataset_version_id=UUID(
            "11111111-1111-1111-1111-111111111111"
        ),
        training_dataset_manifest_digest="a" * 64,
        evaluation_dataset_version_id=UUID(
            "22222222-2222-2222-2222-222222222222"
        ),
        evaluation_dataset_manifest_digest="b" * 64,
    )



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
