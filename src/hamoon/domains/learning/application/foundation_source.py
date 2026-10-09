from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from hamoon.domains.learning.domain.entities import (
    DatasetSourceKind,
    LearningDatasetItem,
    LearningDatasetVersion,
)
from hamoon.domains.learning.domain.errors import LearningDatasetError
from hamoon.infrastructure.ai.contracts import AITaskClass


FOUNDATION_SOURCE_SELECTION_POLICY_VERSION = "approved-foundation-source-import-v1"


class _HumanApproval(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    scope: str


class _TaskSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_class: str
    path: str
    example_count: int


class _FoundationManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str
    status: str
    approval_state: str
    contains_production_household_data: bool
    contains_hidden_chain_of_thought: bool
    human_approval: _HumanApproval
    task_sources: list[_TaskSource]


class _SourceExample(BaseModel):
    model_config = ConfigDict(extra="ignore")

    example_id: str
    input_payload: dict[str, JsonValue]
    target_payload: dict[str, JsonValue]


class _TaskDataset(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dataset_key: str
    version: str
    task_class: str
    status: str
    contains_production_household_data: bool
    contains_hidden_chain_of_thought: bool
    examples: list[_SourceExample]


@dataclass(frozen=True, slots=True)
class FoundationExample:
    example_id: str
    input_payload: dict[str, JsonValue]
    target_payload: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class ApprovedFoundationSource:
    task_class: AITaskClass
    dataset_key: str
    version: str
    source_ref: str
    source_digest: str
    approval_ref: str
    examples: tuple[FoundationExample, ...]


_TASK_FILE_BY_CLASS: dict[AITaskClass, str] = {
    AITaskClass.DIAGNOSIS: "diagnosis.json",
    AITaskClass.OUTCOME_INTERPRETATION: "outcome_interpretation.json",
}

_APPROVAL_REF_BY_VERSION = {
    "v1": (
        "repo://docs/approvals/"
        "HAMOON-FOUNDATION-BEHAVIOR-DATASET-V1-HUMAN-APPROVAL.md"
    ),
}


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_example(
    *,
    task_class: AITaskClass,
    example: _SourceExample,
) -> None:
    if not example.example_id.strip():
        raise LearningDatasetError("FOUNDATION_EXAMPLE_ID_REQUIRED")
    flags = example.target_payload.get("review_flags")
    if not isinstance(flags, list) or "HUMAN_REVIEW_REQUIRED" not in flags:
        raise LearningDatasetError("FOUNDATION_HUMAN_REVIEW_FLAG_REQUIRED")

    if task_class is AITaskClass.DIAGNOSIS:
        if example.target_payload.get("schema_version") != "diagnosis-v1":
            raise LearningDatasetError("FOUNDATION_DIAGNOSIS_SCHEMA_MISMATCH")
        items = example.target_payload.get("items")
        if not isinstance(items, list):
            raise LearningDatasetError("FOUNDATION_DIAGNOSIS_ITEMS_INVALID")
        for raw_item in items:
            if not isinstance(raw_item, dict):
                raise LearningDatasetError("FOUNDATION_DIAGNOSIS_ITEM_INVALID")
            refs = raw_item.get("supporting_feature_refs")
            if not isinstance(refs, list):
                raise LearningDatasetError("FOUNDATION_GROUNDING_REQUIRED")
            for ref in refs:
                if not isinstance(ref, str) or ref not in example.input_payload:
                    raise LearningDatasetError("FOUNDATION_GROUNDING_INVALID")
        return

    if task_class is AITaskClass.OUTCOME_INTERPRETATION:
        if (
            example.target_payload.get("schema_version")
            != "outcome-interpretation-v1"
        ):
            raise LearningDatasetError("FOUNDATION_OUTCOME_SCHEMA_MISMATCH")
        if example.input_payload.get("policy.causal_claim_allowed") is not False:
            raise LearningDatasetError("FOUNDATION_CAUSAL_POLICY_INVALID")
        if example.target_payload.get("causal_claim") is not False:
            raise LearningDatasetError("FOUNDATION_CAUSAL_CLAIM_NOT_ALLOWED")
        refs = example.target_payload.get("supporting_feature_refs")
        if not isinstance(refs, list) or not refs:
            raise LearningDatasetError("FOUNDATION_GROUNDING_REQUIRED")
        for ref in refs:
            if not isinstance(ref, str) or ref not in example.input_payload:
                raise LearningDatasetError("FOUNDATION_GROUNDING_INVALID")
        return

    raise LearningDatasetError("FOUNDATION_TASK_CLASS_UNSUPPORTED")


class FoundationSourceLoader:
    def __init__(
        self,
        root: Path = Path("training/foundation"),
        repository_root: Path = Path("."),
    ) -> None:
        self._root = root
        self._repository_root = repository_root

    def load(
        self,
        *,
        task_class: AITaskClass,
        source_version: str,
    ) -> ApprovedFoundationSource:
        filename = _TASK_FILE_BY_CLASS.get(task_class)
        approval_ref = _APPROVAL_REF_BY_VERSION.get(source_version)
        if filename is None:
            raise LearningDatasetError("FOUNDATION_TASK_CLASS_UNSUPPORTED")
        if approval_ref is None:
            raise LearningDatasetError("FOUNDATION_SOURCE_VERSION_UNSUPPORTED")

        version_dir = self._root / source_version
        manifest_path = version_dir / "manifest.json"
        behavior_contract_path = version_dir / "behavior_contract.json"
        task_path = version_dir / filename
        approval_relative_path = approval_ref.removeprefix("repo://")
        approval_path = self._repository_root / approval_relative_path
        try:
            manifest_bytes = manifest_path.read_bytes()
            behavior_contract_bytes = behavior_contract_path.read_bytes()
            task_bytes = task_path.read_bytes()
            approval_bytes = approval_path.read_bytes()
            manifest = _FoundationManifest.model_validate_json(
                manifest_bytes
            )
            task_dataset = _TaskDataset.model_validate_json(
                task_bytes
            )
        except FileNotFoundError as exc:
            raise LearningDatasetError("FOUNDATION_SOURCE_FILE_MISSING") from exc
        except (OSError, ValidationError) as exc:
            raise LearningDatasetError("FOUNDATION_SOURCE_INVALID") from exc

        if (
            manifest.version != source_version
            or manifest.status != "APPROVED_SOURCE_ONLY"
            or manifest.approval_state != "HUMAN_APPROVED_SOURCE"
            or manifest.human_approval.status != "APPROVED"
            or manifest.human_approval.scope != "FOUNDATION_SOURCE_CONTENT"
        ):
            raise LearningDatasetError("FOUNDATION_SOURCE_NOT_HUMAN_APPROVED")
        if (
            manifest.contains_production_household_data
            or manifest.contains_hidden_chain_of_thought
        ):
            raise LearningDatasetError("FOUNDATION_SOURCE_POLICY_VIOLATION")

        expected_repo_path = f"training/foundation/{source_version}/{filename}"
        task_entry = next(
            (
                item
                for item in manifest.task_sources
                if item.task_class == task_class.value
            ),
            None,
        )
        if (
            task_entry is None
            or task_entry.path != expected_repo_path
            or task_entry.example_count != len(task_dataset.examples)
        ):
            raise LearningDatasetError("FOUNDATION_SOURCE_MANIFEST_MISMATCH")

        if (
            task_dataset.version != source_version
            or task_dataset.task_class != task_class.value
            or task_dataset.status != "APPROVED_SOURCE_ONLY"
            or not task_dataset.dataset_key.strip()
            or not task_dataset.examples
        ):
            raise LearningDatasetError("FOUNDATION_SOURCE_DATASET_MISMATCH")
        if (
            task_dataset.contains_production_household_data
            or task_dataset.contains_hidden_chain_of_thought
        ):
            raise LearningDatasetError("FOUNDATION_SOURCE_POLICY_VIOLATION")

        seen: set[str] = set()
        examples: list[FoundationExample] = []
        for example in task_dataset.examples:
            _validate_example(task_class=task_class, example=example)
            if example.example_id in seen:
                raise LearningDatasetError("FOUNDATION_EXAMPLE_ID_DUPLICATE")
            seen.add(example.example_id)
            examples.append(
                FoundationExample(
                    example_id=example.example_id,
                    input_payload=dict(example.input_payload),
                    target_payload=dict(example.target_payload),
                )
            )

        digest = hashlib.sha256()
        for relative_name, content in (
            ("manifest.json", manifest_bytes),
            ("behavior_contract.json", behavior_contract_bytes),
            (filename, task_bytes),
            (approval_relative_path, approval_bytes),
        ):
            digest.update(relative_name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(content)
            digest.update(b"\0")
        source_digest = digest.hexdigest()
        return ApprovedFoundationSource(
            task_class=task_class,
            dataset_key=task_dataset.dataset_key.strip(),
            version=task_dataset.version,
            source_ref=f"repo://{expected_repo_path}",
            source_digest=source_digest,
            approval_ref=approval_ref,
            examples=tuple(examples),
        )


def foundation_source_refs(
    source: ApprovedFoundationSource,
    *,
    example_id: str,
) -> tuple[str, ...]:
    return (
        f"foundation_dataset:{source.dataset_key}:{source.version}",
        f"foundation_example:{example_id}",
        f"foundation_source_sha256:{source.source_digest}",
        f"foundation_approval:{source.approval_ref}",
    )


def foundation_runtime_manifest_digest(
    source: ApprovedFoundationSource,
) -> str:
    items = [
        {
            "source_key": example.example_id,
            "input": example.input_payload,
            "target": example.target_payload,
            "source_refs": list(
                foundation_source_refs(source, example_id=example.example_id)
            ),
        }
        for example in source.examples
    ]
    return _canonical_digest(
        {
            "dataset_key": source.dataset_key,
            "version": source.version,
            "purpose": source.task_class.value,
            "selection_policy_version": FOUNDATION_SOURCE_SELECTION_POLICY_VERSION,
            "source_kind": DatasetSourceKind.APPROVED_FOUNDATION_SOURCE.value,
            "source_ref": source.source_ref,
            "source_digest": source.source_digest,
            "source_approval_ref": source.approval_ref,
            "items": items,
        }
    )


def attest_foundation_dataset(
    *,
    dataset: LearningDatasetVersion,
    items: list[LearningDatasetItem] | tuple[LearningDatasetItem, ...],
    source: ApprovedFoundationSource,
) -> None:
    if (
        dataset.source_kind is not DatasetSourceKind.APPROVED_FOUNDATION_SOURCE
        or dataset.dataset_key != source.dataset_key
        or dataset.version != source.version
        or dataset.purpose != source.task_class.value
        or dataset.selection_policy_version
        != FOUNDATION_SOURCE_SELECTION_POLICY_VERSION
        or dataset.source_ref != source.source_ref
        or dataset.source_digest != source.source_digest
        or dataset.source_approval_ref != source.approval_ref
        or dataset.manifest_digest != foundation_runtime_manifest_digest(source)
        or len(items) != len(source.examples)
    ):
        raise LearningDatasetError("FOUNDATION_SOURCE_ATTESTATION_MISMATCH")

    for ordinal, (item, example) in enumerate(
        zip(items, source.examples, strict=True),
        start=1,
    ):
        if (
            item.ordinal != ordinal
            or item.learning_signal_id is not None
            or item.signal_type is not None
            or item.signal_label is not None
            or item.source_key != example.example_id
            or item.input_payload != example.input_payload
            or item.target_payload != example.target_payload
            or item.source_refs
            != foundation_source_refs(source, example_id=example.example_id)
        ):
            raise LearningDatasetError("FOUNDATION_SOURCE_ATTESTATION_MISMATCH")
