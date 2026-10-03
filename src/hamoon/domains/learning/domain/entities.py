from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import LearningSignalType


class DatasetVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    RETIRED = "RETIRED"


@dataclass(frozen=True, slots=True)
class LearningDatasetVersion:
    id: UUID
    dataset_key: str
    version: str
    purpose: str
    selection_policy_version: str
    status: DatasetVersionStatus
    manifest_ref: str
    manifest_digest: str
    created_at: datetime
    created_by: UUID
    approved_at: datetime | None = None
    approved_by: UUID | None = None

    def approve(
        self,
        *,
        approved_at: datetime,
        approved_by: UUID,
    ) -> "LearningDatasetVersion":
        if self.status is not DatasetVersionStatus.DRAFT:
            raise ValueError("DATASET_NOT_DRAFT")
        return replace(
            self,
            status=DatasetVersionStatus.APPROVED,
            approved_at=approved_at,
            approved_by=approved_by,
        )


@dataclass(frozen=True, slots=True)
class LearningDatasetItem:
    id: UUID
    dataset_version_id: UUID
    ordinal: int
    learning_signal_id: UUID
    signal_type: LearningSignalType
    signal_label: str
    input_payload: dict[str, JsonValue]
    target_payload: dict[str, JsonValue]
    source_refs: tuple[str, ...]
