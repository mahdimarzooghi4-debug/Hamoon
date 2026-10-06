from __future__ import annotations

from pathlib import Path

from hamoon.infrastructure.ai.contracts import (
    ProviderStructuredRequest,
    ProviderStructuredResponse,
)
from hamoon.infrastructure.ai.native_model import (
    NativeModelArtifactError,
    infer_from_artifact,
    load_artifact,
)


class HamoonNativeAIProviderError(RuntimeError):
    """Native Hamoon model execution failed safely."""


class HamoonNativeAIProvider:
    code = "HAMOON_NATIVE"

    def __init__(self, *, model_root: str) -> None:
        root = Path(model_root)
        if not root.is_absolute():
            raise ValueError("NATIVE_AI_MODEL_ROOT_MUST_BE_ABSOLUTE")
        self._root = root

    async def generate_structured(
        self,
        request: ProviderStructuredRequest,
    ) -> ProviderStructuredResponse:
        digest = request.model_artifact_sha256
        if digest is None:
            raise HamoonNativeAIProviderError(
                "NATIVE_MODEL_ARTIFACT_DIGEST_REQUIRED"
            )
        try:
            artifact = load_artifact(root=self._root, digest=digest)
            output = infer_from_artifact(
                artifact=artifact,
                task_class=request.task_class,
                model_id=request.model_id,
                feature_schema_version=request.feature_schema_version,
                output_schema_version=request.output_schema_version,
                features=request.features,
            )
        except NativeModelArtifactError as exc:
            raise HamoonNativeAIProviderError(str(exc)) from exc

        return ProviderStructuredResponse(
            provider_code=self.code,
            model_id=request.model_id,
            model_artifact_sha256=digest,
            output=output,
        )
