import json
from typing import cast

import httpx
from pydantic import JsonValue
from hamoon.infrastructure.ai.contracts import (
    ProviderStructuredRequest,
    ProviderStructuredResponse,
)


class OpenAIProviderError(RuntimeError):
    """OpenAI Responses API request or response failed safely."""


class OpenAIProvider:
    code = "OPENAI"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def generate_structured(
        self,
        request: ProviderStructuredRequest,
    ) -> ProviderStructuredResponse:
        payload: dict[str, JsonValue] = {
            "model": request.model_id,
            "store": False,
            "instructions": request.instructions,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Return only a structured JSON proposal for the Hamoon "
                                f"task {request.task_class.value}, grounded in the provided "
                                "versioned feature package. Do not invent missing facts, "
                                "do not change authoritative PGOR values, and preserve "
                                "human-review boundaries. Feature package:\n"
                                + json.dumps(
                                    request.features,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                )
                            ),
                        }
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": request.output_schema_version.replace("-", "_"),
                    "strict": True,
                    "schema": request.output_schema,
                }
            },
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Client-Request-Id": request.correlation_id,
        }

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            response = await client.post(
                f"{self._base_url}/responses",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            raw_body = cast(object, response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise OpenAIProviderError("AI_PROVIDER_REQUEST_FAILED") from exc
        finally:
            if owns_client:
                await client.aclose()

        if not isinstance(raw_body, dict):
            raise OpenAIProviderError("AI_PROVIDER_RESPONSE_NOT_OBJECT")
        body = cast(dict[str, object], raw_body)

        text_output = self._extract_output_text(body)
        try:
            parsed_raw = cast(object, json.loads(text_output))
        except json.JSONDecodeError as exc:
            raise OpenAIProviderError("AI_PROVIDER_OUTPUT_NOT_JSON") from exc
        if not isinstance(parsed_raw, dict):
            raise OpenAIProviderError("AI_PROVIDER_OUTPUT_NOT_OBJECT")
        parsed = cast(dict[str, JsonValue], parsed_raw)

        return ProviderStructuredResponse(
            provider_code=self.code,
            model_id=request.model_id,
            output=parsed,
        )

    @staticmethod
    def _extract_output_text(body: dict[str, object]) -> str:
        outputs = body.get("output")
        if not isinstance(outputs, list):
            raise OpenAIProviderError("AI_PROVIDER_OUTPUT_MISSING")

        chunks: list[str] = []
        for item in cast(list[object], outputs):
            if not isinstance(item, dict):
                continue
            item_object = cast(dict[str, object], item)
            content = item_object.get("content")
            if not isinstance(content, list):
                continue
            for part in cast(list[object], content):
                if not isinstance(part, dict):
                    continue
                part_object = cast(dict[str, object], part)
                if part_object.get("type") == "refusal":
                    raise OpenAIProviderError("AI_PROVIDER_REFUSED")
                if part_object.get("type") == "output_text":
                    value = part_object.get("text")
                    if isinstance(value, str):
                        chunks.append(value)

        if not chunks:
            raise OpenAIProviderError("AI_PROVIDER_OUTPUT_MISSING")
        return "".join(chunks)
