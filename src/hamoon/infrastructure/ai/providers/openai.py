import json
from typing import Any

import httpx
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
        payload: dict[str, Any] = {
            "model": request.model_id,
            "instructions": request.instructions,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Return only a JSON diagnosis proposal grounded in the "
                                "provided Hamoon feature package. Do not invent missing "
                                "facts. Feature package:\n"
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
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OpenAIProviderError("AI_PROVIDER_REQUEST_FAILED") from exc
        finally:
            if owns_client:
                await client.aclose()

        text_output = self._extract_output_text(body)
        try:
            parsed = json.loads(text_output)
        except json.JSONDecodeError as exc:
            raise OpenAIProviderError("AI_PROVIDER_OUTPUT_NOT_JSON") from exc
        if not isinstance(parsed, dict):
            raise OpenAIProviderError("AI_PROVIDER_OUTPUT_NOT_OBJECT")

        return ProviderStructuredResponse(
            provider_code=self.code,
            model_id=request.model_id,
            output=parsed,
        )

    @staticmethod
    def _extract_output_text(body: dict[str, Any]) -> str:
        outputs = body.get("output")
        if not isinstance(outputs, list):
            raise OpenAIProviderError("AI_PROVIDER_OUTPUT_MISSING")

        chunks: list[str] = []
        for item in outputs:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "refusal":
                    raise OpenAIProviderError("AI_PROVIDER_REFUSED")
                if part.get("type") == "output_text":
                    value = part.get("text")
                    if isinstance(value, str):
                        chunks.append(value)

        if not chunks:
            raise OpenAIProviderError("AI_PROVIDER_OUTPUT_MISSING")
        return "".join(chunks)
