from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, JsonValue

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
from hamoon.infrastructure.ai.providers.native import HamoonNativeAIProvider


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


def _runtime_features(case: OutcomeEvaluationCase) -> dict[str, JsonValue]:
    source = case.input
    pre = source.get("pre_pgor")
    post = source.get("post_pgor")
    delta = source.get("delta")
    if not isinstance(pre, dict) or not isinstance(post, dict) or not isinstance(delta, dict):
        raise ValueError("Outcome evaluation case PGOR blocks are invalid.")

    def value(block: dict[str, JsonValue], key: str) -> JsonValue:
        if key not in block:
            raise ValueError(f"Outcome evaluation case missing {key}.")
        return block[key]

    return {
        "pgor.pre.P": value(pre, "p"),
        "pgor.pre.G": value(pre, "g"),
        "pgor.pre.O": value(pre, "o"),
        "pgor.pre.R": value(pre, "r"),
        "pgor.pre.E": value(pre, "e"),
        "pgor.post.P": value(post, "p"),
        "pgor.post.G": value(post, "g"),
        "pgor.post.O": value(post, "o"),
        "pgor.post.R": value(post, "r"),
        "pgor.post.E": value(post, "e"),
        "pgor.delta.P": value(delta, "p"),
        "pgor.delta.G": value(delta, "g"),
        "pgor.delta.O": value(delta, "o"),
        "pgor.delta.R": value(delta, "r"),
        "pgor.delta.E": value(delta, "e"),
        "intervention.type": source.get("intervention_type"),
        "intervention.target_variable": source.get("target_pgor_variable"),
        "provider_result.type": source.get("provider_result_type"),
        "provider_result.status": source.get("provider_result_status"),
        "outcome.methodology_version": source.get("methodology_version"),
        "policy.causal_claim_allowed": source.get("causal_claim_allowed"),
    }


async def run_candidate_evaluation(
    *,
    model_root: str,
    model_artifact_sha256: str,
    model_id: str,
    model_alias: str,
    prompt_policy_version: str,
    output_schema_version: str,
    instructions: str,
    dataset_version: str,
    cases: list[OutcomeEvaluationCase],
    policy: OutcomeEvaluationPolicy,
) -> tuple[OutcomeCandidateEvaluationBundle, OutcomeEvaluationReport]:
    provider = HamoonNativeAIProvider(model_root=model_root)
    outputs: list[OutcomeEvaluationOutput] = []
    for case in cases:
        response = await provider.generate_structured(
            ProviderStructuredRequest(
                task_class=AITaskClass.OUTCOME_INTERPRETATION,
                model_id=model_id,
                model_alias=model_alias,
                prompt_policy_version=prompt_policy_version,
                output_schema_version=output_schema_version,
                feature_schema_version="outcome-input-v1",
                instructions=instructions,
                output_schema=OUTCOME_INTERPRETATION_V1_SCHEMA,
                features=_runtime_features(case),
                correlation_id=f"eval:{dataset_version}:{case.case_id}",
                model_artifact_sha256=model_artifact_sha256,
            )
        )
        outputs.append(
            OutcomeEvaluationOutput(
                case_id=case.case_id,
                output=response.output,
            )
        )

    bundle = OutcomeCandidateEvaluationBundle(
        provider_code="HAMOON_NATIVE",
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
        description="Run a native Hamoon outcome candidate against an evaluation dataset."
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
    parser.add_argument("--model-artifact-sha256", required=True)
    parser.add_argument(
        "--model-root",
        default=os.getenv("HAMOON_AI_MODEL_ROOT"),
    )
    args = parser.parse_args()

    if not args.model_root:
        raise RuntimeError(
            "HAMOON_AI_MODEL_ROOT or --model-root is required "
            "for native candidate evaluation."
        )

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
        model_root=args.model_root,
        model_artifact_sha256=args.model_artifact_sha256,
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
