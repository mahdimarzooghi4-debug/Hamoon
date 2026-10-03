from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue


class FeaturePackageType(StrEnum):
    DIAGNOSIS = "DIAGNOSIS"


class SensitivityClass(StrEnum):
    INTERNAL = "INTERNAL"
    SENSITIVE = "SENSITIVE"


@dataclass(frozen=True, slots=True)
class FeatureValue:
    key: str
    value: JsonValue
    source_refs: tuple[str, ...]
    sensitivity_class: SensitivityClass = SensitivityClass.INTERNAL


@dataclass(frozen=True, slots=True)
class FeaturePackage:
    id: UUID
    household_id: UUID
    assessment_id: UUID
    pgor_snapshot_id: UUID
    package_type: FeaturePackageType
    schema_version: str
    source_fingerprint: str
    data_quality_flags: tuple[str, ...]
    values: tuple[FeatureValue, ...]
    created_at: datetime
    created_by: UUID

    def provider_payload(self) -> dict[str, JsonValue]:
        return {
            item.key: item.value
            for item in self.values
            if item.sensitivity_class is SensitivityClass.INTERNAL
        }
