from typing import Protocol

from hamoon.infrastructure.ai.contracts import (
    ProviderStructuredRequest,
    ProviderStructuredResponse,
)


class AIProviderAdapter(Protocol):
    code: str

    async def generate_structured(
        self,
        request: ProviderStructuredRequest,
    ) -> ProviderStructuredResponse: ...
