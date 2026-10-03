from uuid import UUID

import pytest

from hamoon.infrastructure.ai.contracts import (
    AIRoutingPolicy,
    AITaskClass,
    StructuredAIRequest,
)
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.providers.fake import FakeAIProvider

POLICY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PACKAGE_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "summary", "items", "review_flags"],
    "properties": {
        "schema_version": {"const": "diagnosis-v1"},
        "summary": {"type": "string"},
        "items": {"type": "array"},
        "review_flags": {"type": "array"},
    },
}


@pytest.mark.asyncio
async def test_fake_provider_runs_through_schema_validating_gateway() -> None:
    gateway = ProviderAIGateway(providers={"FAKE": FakeAIProvider()})
    policy = AIRoutingPolicy(
        id=POLICY_ID,
        version="local-v1",
        task_class=AITaskClass.DIAGNOSIS,
        provider_code="FAKE",
        model_alias="hamoon.diagnosis.v1",
        concrete_model_id="fake-diagnosis-v1",
        prompt_policy_version="diagnosis-prompt-v1",
        output_schema_version="diagnosis-v1",
    )

    result = await gateway.generate_structured(
        request=StructuredAIRequest(
            task_class=AITaskClass.DIAGNOSIS,
            feature_package_id=PACKAGE_ID,
            feature_schema_version="diagnosis-input-v1",
            features={"pgor.bottleneck_variables": ["P"]},
            correlation_id="corr-1",
        ),
        routing_policy=policy,
        output_schema=SCHEMA,
    )

    assert result.feature_package_id == PACKAGE_ID
    assert result.feature_schema_version == "diagnosis-input-v1"
    assert result.provider_code == "FAKE"
    assert result.model_alias == "hamoon.diagnosis.v1"
    assert result.output["schema_version"] == "diagnosis-v1"
    assert result.output["review_flags"] == [
        "FAKE_PROVIDER",
        "HUMAN_REVIEW_REQUIRED",
    ]
