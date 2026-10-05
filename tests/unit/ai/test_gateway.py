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



@pytest.mark.asyncio
async def test_ai_gateway_span_carries_business_correlation(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Span:
        def set_attribute(self, key: str, value: object) -> None:
            captured[key] = value

        def record_exception(self, _exc: Exception) -> None:
            pass

        def end(self) -> None:
            captured["ended"] = True

    class _Tracer:
        def start_span(self, name: str, *, attributes: dict[str, object]):
            captured["span_name"] = name
            captured.update(attributes)
            return _Span()

    import hamoon.infrastructure.ai.gateway as gateway_module

    monkeypatch.setattr(gateway_module, "_tracer", _Tracer())

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
    await gateway.generate_structured(
        request=StructuredAIRequest(
            task_class=AITaskClass.DIAGNOSIS,
            feature_package_id=PACKAGE_ID,
            feature_schema_version="diagnosis-input-v1",
            features={"pgor.bottleneck_variables": ["P"]},
            correlation_id="corr-observability-contract",
        ),
        routing_policy=policy,
        output_schema=SCHEMA,
    )

    assert captured["span_name"] == "hamoon.ai.generate_structured"
    assert captured["hamoon.correlation_id"] == "corr-observability-contract"
    assert captured["hamoon.ai.task_class"] == "DIAGNOSIS"
    assert captured["hamoon.ai.status"] == "success"
    assert captured["ended"] is True
