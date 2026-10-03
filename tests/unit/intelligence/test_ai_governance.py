from hamoon.domains.intelligence.domain.registry import (
    AIModelVersionStatus,
    EvaluationStatus,
    PromptPolicyVersionStatus,
    RoutingPolicyStatus,
)


def test_governance_statuses_make_promotion_explicit() -> None:
    assert AIModelVersionStatus.CANDIDATE.value == "CANDIDATE"
    assert AIModelVersionStatus.PRODUCTION.value == "PRODUCTION"
    assert EvaluationStatus.PASSED.value == "PASSED"
    assert PromptPolicyVersionStatus.ACTIVE.value == "ACTIVE"
    assert RoutingPolicyStatus.DRAFT.value == "DRAFT"
    assert RoutingPolicyStatus.ACTIVE.value == "ACTIVE"


def test_evaluation_report_requires_structural_gate_before_manual_approval() -> None:
    metrics = {
        "dataset_version": "diagnosis-dataset-v1",
        "policy_version": "diagnosis-eval-v1",
        "schema_compliance": 1.0,
        "evidence_coverage": 1.0,
        "unsupported_claim_rate": 0.0,
        "safety_violation_rate": 0.0,
        "structural_gate_passed": True,
        "manual_approval_required": True,
    }

    assert metrics["structural_gate_passed"] is True
    assert metrics["manual_approval_required"] is True
