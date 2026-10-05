from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.intelligence.api import routes as intelligence_routes
from hamoon.domains.intelligence.domain.registry import (
    AIModelVersionCatalogItem,
    AIModelVersionStatus,
    AIProviderStatus,
    EvaluationRunState,
    EvaluationStatus,
    PromptPolicyVersionCatalogItem,
    PromptPolicyVersionStatus,
    RoutingPolicyCatalogItem,
    RoutingPolicyStatus,
)
from hamoon.infrastructure.ai.contracts import AITaskClass

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
MODEL_ID = UUID("22222222-2222-2222-2222-222222222222")
AI_MODEL_ID = UUID("33333333-3333-3333-3333-333333333333")
PROVIDER_ID = UUID("44444444-4444-4444-4444-444444444444")
PROMPT_ID = UUID("55555555-5555-5555-5555-555555555555")
PROMPT_POLICY_ID = UUID("66666666-6666-6666-6666-666666666666")
EVAL_ID = UUID("77777777-7777-7777-7777-777777777777")
DATASET_ID = UUID("88888888-8888-8888-8888-888888888888")
ROUTE_ID = UUID("99999999-9999-9999-9999-999999999999")


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="admin",
        issuer="https://identity.local",
        roles=frozenset({Role.ADMIN}),
        scopes=frozenset(),
    )


class Registry:
    async def list_model_versions(self) -> list[AIModelVersionCatalogItem]:
        return [
            AIModelVersionCatalogItem(
                id=MODEL_ID,
                ai_model_id=AI_MODEL_ID,
                model_key="outcome-model",
                purpose="OUTCOME_INTERPRETATION",
                provider_id=PROVIDER_ID,
                provider_code="HAMOON_LOCAL",
                provider_status=AIProviderStatus.ACTIVE,
                version="v2",
                concrete_model_id="model-v2",
                artifact_ref="outcome/v2",
                artifact_sha256="a" * 64,
                parent_model_version_id=None,
                training_dataset_version_id=DATASET_ID,
                training_dataset_manifest_digest="b" * 64,
                training_recipe_version="outcome-train-v2",
                trained_at=datetime(2026, 10, 4, tzinfo=UTC),
                status=AIModelVersionStatus.CANDIDATE,
                limitations=None,
                approved_at=None,
                deployed_at=None,
            )
        ]

    async def list_prompt_policy_versions(
        self,
    ) -> list[PromptPolicyVersionCatalogItem]:
        return [
            PromptPolicyVersionCatalogItem(
                id=PROMPT_ID,
                prompt_policy_id=PROMPT_POLICY_ID,
                policy_name="outcome-prompt",
                purpose="OUTCOME_INTERPRETATION",
                version="v3",
                output_schema_version="outcome-interpretation-v1",
                guardrail_version="guard-v1",
                status=PromptPolicyVersionStatus.ACTIVE,
                approved_at=datetime(2026, 10, 1, tzinfo=UTC),
            )
        ]

    async def list_evaluation_runs(
        self,
        *,
        task_class: AITaskClass | None = None,
        limit: int = 100,
    ) -> list[EvaluationRunState]:
        assert task_class is AITaskClass.OUTCOME_INTERPRETATION
        assert limit == 10
        return [
            EvaluationRunState(
                id=EVAL_ID,
                task_class=AITaskClass.OUTCOME_INTERPRETATION,
                model_version_id=MODEL_ID,
                prompt_policy_version_id=PROMPT_ID,
                evaluation_policy_version="outcome-eval-v1",
                dataset_version_id=DATASET_ID,
                dataset_manifest_digest="a" * 64,
                report_digest="b" * 64,
                status=EvaluationStatus.PASSED,
                passed=True,
                summary_metrics={"structural_gate_passed": True},
                started_at=datetime(2026, 10, 4, tzinfo=UTC),
                completed_at=datetime(2026, 10, 4, 1, tzinfo=UTC),
            )
        ]

    async def list_routing_policies(
        self,
        *,
        task_class: AITaskClass | None = None,
        limit: int = 100,
    ) -> list[RoutingPolicyCatalogItem]:
        assert task_class is AITaskClass.OUTCOME_INTERPRETATION
        assert limit == 10
        return [
            RoutingPolicyCatalogItem(
                id=ROUTE_ID,
                task_class=AITaskClass.OUTCOME_INTERPRETATION,
                version="route-v4",
                model_alias="hamoon.outcome.v2",
                model_version_id=MODEL_ID,
                prompt_policy_version_id=PROMPT_ID,
                evaluation_run_id=EVAL_ID,
                structured_output_required=True,
                status=RoutingPolicyStatus.DRAFT,
                approved_at=None,
            )
        ]


@pytest.mark.asyncio
async def test_admin_governance_catalog_read_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        intelligence_routes,
        "SqlAlchemyAIRuntimeRegistryRepository",
        lambda _session: Registry(),
    )
    session = cast(AsyncSession, object())
    context = _context()

    models = await intelligence_routes.list_ai_model_versions(context, session)
    prompts = await intelligence_routes.list_prompt_policy_versions(context, session)
    evaluations = await intelligence_routes.list_ai_evaluations(
        context,
        session,
        task_class=AITaskClass.OUTCOME_INTERPRETATION,
        limit=10,
    )
    routes = await intelligence_routes.list_ai_routing_policies(
        context,
        session,
        task_class=AITaskClass.OUTCOME_INTERPRETATION,
        limit=10,
    )

    assert models.data[0].status == AIModelVersionStatus.CANDIDATE.value
    assert models.data[0].provider_code == "HAMOON_LOCAL"
    assert models.data[0].artifact_sha256 == "a" * 64
    assert prompts.data[0].status == PromptPolicyVersionStatus.ACTIVE.value
    assert evaluations.data[0].status == EvaluationStatus.PASSED.value
    assert evaluations.data[0].dataset_version_id == DATASET_ID
    assert routes.data[0].status == RoutingPolicyStatus.DRAFT.value
