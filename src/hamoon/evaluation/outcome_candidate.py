from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from hamoon.evaluation.outcome import (
    OutcomeEvaluationCase,
    OutcomeEvaluationOutput,
    OutcomeEvaluationPolicy,
    OutcomeEvaluationReport,
    evaluate_outcome_outputs,
)
from hamoon.infrastructure.ai.contracts import (
    AITaskClass,
    ProviderStructuredRequest,
)
from hamoon.infrastructure.ai.outcome_runtime import OUTCOME_INTERPRETATION_V1_SCHEMA
from hamoon.infrastructure.ai.providers.openai import OpenAIProvider


class OutcomeCandidateEvaluationBundle(BaseModel):
    provider_code: str
    model_id: str
    model_alias: str
    prompt_policy_version: str
    output_schema_version: str
    dataset_version: str
    generated_at: datetime
    outputs: list[OutcomeEvaluationOutput]


def _load_object(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        raw = cast(object, json.load(handle))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return cast(dict[str, object], raw)


async def run_candidate_evaluation(
    *,
    api_key: str,
    base_url: str,
    model_id: str,
    model_alias: str,
    prompt_policy_version: str,
    output_schema_version: str,
    instructions: str,
    dataset_version: str,
    cases: list[OutcomeEvaluationCase],
    policy: OutcomeEvaluationPolicy,
) -> tuple[OutcomeCandidateEvaluationBundle, OutcomeEvaluationReport]:
    provider = OpenAIProvider(
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=90.0,
    )
    outputs: list[OutcomeEvaluationOutput] = []
    for case in cases:
        response = await provider.generate_structured(
            ProviderStructuredRequest(
                task_class=AITaskClass.OUTCOME_INTERPRETATION,
                model_id=model_id,
                model_alias=model_alias,
                prompt_policy_version=prompt_policy_version,
                output_schema_version=output_schema_version,
                feature_schema_version="outcome-learning-input-v1",
                instructions=instructions,
                output_schema=OUTCOME_INTERPRETATION_V1_SCHEMA,
                features=case.input,
                correlation_id=f"eval:{dataset_version}:{case.case_id}",
            )
        )
        outputs.append(
            OutcomeEvaluationOutput(
                case_id=case.case_id,
                output=response.output,
            )
        )

    bundle = OutcomeCandidateEvaluationBundle(
        provider_code="OPENAI",
        model_id=model_id,
        model_alias=model_alias,
        prompt_policy_version=prompt_policy_version,
        output_schema_version=output_schema_version,
        dataset_version=dataset_version,
        generated_at=datetime.now(UTC),
        outputs=outputs,
    )
    report = evaluate_outcome_outputs(
        dataset_version=dataset_version,
        cases=cases,
        outputs=outputs,
        policy=policy,
    )
    return bundle, report


async def _async_main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a Hamoon outcome candidate against an exported curated dataset."
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--instructions", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-alias", default="hamoon.outcome.v1")
    parser.add_argument("--prompt-policy-version", default="outcome-prompt-v1")
    parser.add_argument("--output-schema-version", default="outcome-interpretation-v1")
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for candidate evaluation.")

    dataset = _load_object(args.dataset)
    policy = OutcomeEvaluationPolicy.model_validate(_load_object(args.policy))
    raw_cases = dataset.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("Outcome evaluation dataset cases must be a JSON array.")
    dataset_version = str(dataset.get("dataset_version", "unknown"))
    cases = [
        OutcomeEvaluationCase.model_validate(item)
        for item in cast(list[object], raw_cases)
    ]
    instructions = args.instructions.read_text(encoding="utf-8").strip()
    if not instructions:
        raise ValueError("Outcome evaluation instructions must not be empty.")

    bundle, report = await run_candidate_evaluation(
        api_key=api_key,
        base_url=args.base_url,
        model_id=args.model_id,
        model_alias=args.model_alias,
        prompt_policy_version=args.prompt_policy_version,
        output_schema_version=args.output_schema_version,
        instructions=instructions,
        dataset_version=dataset_version,
        cases=cases,
        policy=policy,
    )
    args.outputs.parent.mkdir(parents=True, exist_ok=True)
    args.outputs.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return 0 if report.structural_gate_passed else 2


def main() -> None:
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
