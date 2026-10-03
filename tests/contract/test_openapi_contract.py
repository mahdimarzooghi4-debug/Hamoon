from hamoon.app.main import create_app


def test_openapi_preserves_core_decision_learning_path() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]

    required = {
        "/api/v1/households",
        "/api/v1/households/{household_id}/facts",
        "/api/v1/households/{household_id}/accepted-state/{fact_type}/resolve",
        "/api/v1/assessments/{assessment_id}/calculate-pgor",
        "/api/v1/households/{household_id}/diagnoses/generate",
        "/api/v1/interventions/{intervention_id}/referrals",
        "/api/v1/provider-integrations/referrals/{external_referral_id}/results",
        "/api/v1/work-queue/{work_item_id}/reassessment/start",
        "/api/v1/outcomes/{outcome_id}/confirm",
        "/api/v1/admin/learning/datasets",
        "/api/v1/admin/ai/evaluations",
        "/api/v1/admin/ai/routing-policies/{routing_policy_id}/promote",
        "/api/v1/households/{household_id}/evidence/uploads",
        "/api/v1/admin/health/data",
        "/api/v1/admin/health/machine",
    }
    missing = sorted(required.difference(paths))
    assert missing == []


def test_metrics_is_operational_not_public_api_contract() -> None:
    schema = create_app().openapi()
    assert "/metrics" not in schema["paths"]
