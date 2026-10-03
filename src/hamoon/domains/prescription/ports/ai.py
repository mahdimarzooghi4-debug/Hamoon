from typing import Protocol

from hamoon.domains.intelligence.domain.decisions import AIExecutionResult
from hamoon.domains.intelligence.domain.entities import FeaturePackage


class PrescriptionAIClient(Protocol):
    async def generate_prescription(
        self,
        *,
        feature_package: FeaturePackage,
        correlation_id: str,
    ) -> AIExecutionResult: ...
