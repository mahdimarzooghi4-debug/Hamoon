import json
from uuid import UUID

import httpx
import pytest

from hamoon.infrastructure.ai.contracts import (
    AITaskClass,
    ProviderStructuredRequest,
)
from hamoon.infrastructure.ai.providers.openai import OpenAIProvider


@pytest.mark.asyncio
async def test_openai_provider_uses_responses_structured_output_contract() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "schema_version": "diagnosis-v1",
                                        "summary": "Grounded diagnosis.",
                                        "items": [],
                                        "review_flags": ["HUMAN_REVIEW_REQUIRED"],
                                    }
                                ),
                            }
                        ],
                    }
                ]
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.openai.com",
    )
    provider = OpenAIProvider(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        client=client,
    )

    schema = {
        "type": "object",
        "required": ["schema_version", "summary", "items", "review_flags"],
        "properties": {
            "schema_version": {"const": "diagnosis-v1"},
            "summary": {"type": "string"},
            "items": {"type": "array"},
            "review_flags": {"type": "array"},
        },
    }
    result = await provider.generate_structured(
        ProviderStructuredRequest(
            task_class=AITaskClass.DIAGNOSIS,
            model_id="deployment-model-id",
            model_alias="hamoon.diagnosis.v1",
            prompt_policy_version="diagnosis-prompt-v1",
            output_schema_version="diagnosis-v1",
            feature_schema_version="diagnosis-input-v1",
            instructions="Use only supplied features.",
            output_schema=schema,
            features={"pgor.O": "0.3"},
            correlation_id=str(UUID("11111111-1111-1111-1111-111111111111")),
        )
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert captured["path"] == "/v1/responses"
    assert captured["authorization"] == "Bearer test-key"
    assert payload["model"] == "deployment-model-id"
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert result.output["schema_version"] == "diagnosis-v1"

    await client.aclose()
