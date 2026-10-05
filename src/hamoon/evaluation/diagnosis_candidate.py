from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from hamoon.evaluation.diagnosis import (
    DiagnosisEvaluationCase,
    DiagnosisEvaluationOutput,
    DiagnosisEvaluationPolicy,
    DiagnosisEvaluationReport,
    evaluate_diagnosis_outputs,
)
from hamoon.infrastructure.ai.contracts import (
    AITaskClass,
    ProviderStructuredRequest,
)
from hamoon.infrastructure.ai.diagnosis_runtime import DIAGNOSIS_V1_SCHEMA
from hamoon.infrastructure.ai.providers.local_artifact import LocalArtifactAIProvider


class CandidateEvaluationBundle(BaseModel):
    provider_code: str
    model_id: str
    model_artifact_sha256: str
    model_alias: str
    prompt_policy_version: str
    output_schema_version: str
    dataset_version: str
    generated_at: datetime
    outputs: list[DiagnosisEvaluationOutput]


def _load_json_object(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        raw = cast(object, json.load(handle))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return cast(dict[str, object], raw)


def _load_cases(path: Path) -> tuple[str, list[DiagnosisEvaluationCase]]:
    dataset = _load_json_object(path)
    dataset_version_raw = dataset.get("dataset_version")
    if not isinstance(dataset_version_raw, str) or not dataset_version_raw:
        raise ValueError("Diagnosis dataset_version is required.")

    cases_raw = dataset.get("cases")
    if not isinstance(cases_raw, list):
        raise ValueError("Diagnosis dataset cases must be a JSON array.")

    cases = [
        DiagnosisEvaluationCase.model_validate(item)
        for item in cast(list[object], cases_raw)
    ]
    if not cases:
        raise ValueError("Diagnosis evaluation dataset must not be empty.")
    return dataset_version_raw, cases


def _load_policy(path: Path) -> DiagnosisEvaluationPolicy:
    return DiagnosisEvaluationPolicy.model_validate(_load_json_object(path))


async def run_candidate_evaluation(
    *,
    model_root: Path,
    runner_path: Path,
    model_id: str,
    artifact_ref: str,
    artifact_sha256: str,
    model_alias: str,
    prompt_policy_version: str,
    output_schema_version: str,
    instructions: str,
    dataset_version: str,
    cases: list[DiagnosisEvaluationCase],
    policy: DiagnosisEvaluationPolicy,
) -> tuple[CandidateEvaluationBundle, DiagnosisEvaluationReport]:
    provider = LocalArtifactAIProvider(
        model_root=model_root,
        runner_path=runner_path,
        timeout_seconds=90.0,
    )
    outputs: list[DiagnosisEvaluationOutput] = []

    for case in cases:
        response = await provider.generate_structured(
            ProviderStructuredRequest(
                task_class=AITaskClass.DIAGNOSIS,
                model_id=model_id,
                model_alias=model_alias,
                model_artifact_ref=artifact_ref,
                model_artifact_sha256=artifact_sha256,
                prompt_policy_version=prompt_policy_version,
                output_schema_version=output_schema_version,
                feature_schema_version="diagnosis-input-v1",
                instructions=instructions,
                output_schema=DIAGNOSIS_V1_SCHEMA,
                features=case.features,
                correlation_id=f"eval:{dataset_version}:{case.case_id}",
            )
        )
        outputs.append(
            DiagnosisEvaluationOutput(
                case_id=case.case_id,
                output=response.output,
            )
        )

    generated_at = datetime.now(UTC)
    bundle = CandidateEvaluationBundle(
        provider_code="HAMOON_LOCAL",
        model_id=model_id,
        model_artifact_sha256=artifact_sha256,
        model_alias=model_alias,
        prompt_policy_version=prompt_policy_version,
        output_schema_version=output_schema_version,
        dataset_version=dataset_version,
        generated_at=generated_at,
        outputs=outputs,
    )
    report = evaluate_diagnosis_outputs(
        dataset_version=dataset_version,
        cases=cases,
        outputs=outputs,
        policy=policy,
    )
    return bundle, report


def _write_json(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.model_dump_json(indent=2), encoding="utf-8")


async def _async_main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the real Hamoon diagnosis candidate against the eval dataset."
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--instructions", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-alias", default="hamoon.diagnosis.v1")
    parser.add_argument("--prompt-policy-version", default="diagnosis-prompt-v1")
    parser.add_argument("--output-schema-version", default="diagnosis-v1")
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--runner-path", type=Path, required=True)
    parser.add_argument("--artifact-ref", required=True)
    parser.add_argument(
        "--artifact-sha256",
        required=True,
    )
    args = parser.parse_args()

    if (
        len(args.artifact_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in args.artifact_sha256)
    ):
        raise ValueError("Model artifact SHA-256 must be lowercase hexadecimal.")

    dataset_version, cases = _load_cases(args.dataset)
    policy = _load_policy(args.policy)
    instructions = args.instructions.read_text(encoding="utf-8").strip()
    if not instructions:
        raise ValueError("Diagnosis evaluation instructions must not be empty.")

    bundle, report = await run_candidate_evaluation(
        model_root=args.model_root,
        runner_path=args.runner_path,
        model_id=args.model_id,
        artifact_ref=args.artifact_ref,
        artifact_sha256=args.artifact_sha256,
        model_alias=args.model_alias,
        prompt_policy_version=args.prompt_policy_version,
        output_schema_version=args.output_schema_version,
        instructions=instructions,
        dataset_version=dataset_version,
        cases=cases,
        policy=policy,
    )
    _write_json(args.outputs, bundle)
    _write_json(args.report, report)

    return 0 if report.structural_gate_passed else 2


def main() -> None:
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
