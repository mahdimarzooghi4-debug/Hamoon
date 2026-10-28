#!/usr/bin/env python3
"""Evaluate JSONL structured requests with Hamoon's local Qwen runner.

Each input line is a ProviderStructuredRequest-shaped JSON object. Outputs are
one JSON object per line. The script has no network or production API path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from hamoon.infrastructure.ai.contracts import AITaskClass, ProviderStructuredRequest
from hamoon.infrastructure.ai.qwen35_runtime import (
    QWEN35_BASELINE_REVISION,
    Qwen35OfflineRunner,
)


def _request(raw: object) -> ProviderStructuredRequest:
    if not isinstance(raw, dict):
        raise ValueError("Each JSONL record must be an object")
    value = cast(dict[str, object], raw)
    try:
        task_class = AITaskClass(str(value["task_class"]))
        features = cast(dict[str, JsonValue], value["features"])
        output_schema = cast(dict[str, JsonValue], value["output_schema"])
        if not isinstance(features, dict) or not isinstance(output_schema, dict):
            raise ValueError
        return ProviderStructuredRequest(
            task_class=task_class,
            model_id="Qwen/Qwen3.5-9B",
            model_alias="qwen35-offline",
            prompt_policy_version=str(value.get("prompt_policy_version", "offline-v1")),
            output_schema_version=str(value.get("output_schema_version", "offline-v1")),
            feature_schema_version=str(value["feature_schema_version"]),
            instructions=str(value.get("instructions", "")),
            output_schema=output_schema,
            features=features,
            correlation_id=str(value.get("correlation_id", "offline-eval")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("JSONL record does not match the offline request contract") from exc


async def _run(args: argparse.Namespace) -> int:
    runner = Qwen35OfflineRunner(
        checkpoint_root=Path(args.checkpoint_root),
        revision=args.revision,
        manifest_sha256=args.manifest_sha256,
        max_new_tokens=args.max_new_tokens,
    )
    with Path(args.input).open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                request = _request(json.loads(line))
                result = await runner.generate_structured(request)
            except Exception as exc:
                # Do not include request content in diagnostics; it may contain
                # household information.
                print(
                    json.dumps({"line": line_number, "error": str(exc)}, ensure_ascii=False),
                    file=sys.stderr,
                )
                return 1
            print(json.dumps({"line": line_number, "output": result}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSONL of offline evaluation requests")
    parser.add_argument(
        "--checkpoint-root",
        default=os.environ.get("HAMOON_QWEN35_CHECKPOINT_ROOT"),
        required=os.environ.get("HAMOON_QWEN35_CHECKPOINT_ROOT") is None,
    )
    parser.add_argument(
        "--revision",
        default=os.environ.get(
            "HAMOON_QWEN35_REVISION",
            QWEN35_BASELINE_REVISION,
        ),
        required=False,
    )
    parser.add_argument(
        "--manifest-sha256",
        default=os.environ.get("HAMOON_QWEN35_MANIFEST_SHA256"),
        required=os.environ.get("HAMOON_QWEN35_MANIFEST_SHA256") is None,
    )
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
