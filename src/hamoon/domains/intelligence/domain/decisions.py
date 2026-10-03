from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue


class AIDecisionType(StrEnum):
    DIAGNOSIS = "DIAGNOSIS"
    PRESCRIPTION = "PRESCRIPTION"


class AIDecisionStatus(StrEnum):
    GENERATED = "GENERATED"


class DiagnosisStatus(StrEnum):
    UNDER_REVIEW = "UNDER_REVIEW"
    CONFIRMED = "CONFIRMED"
    MODIFIED = "MODIFIED"
    REPLACED = "REPLACED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


class HumanDecisionContext(StrEnum):
    DIAGNOSIS = "DIAGNOSIS"
    PRESCRIPTION = "PRESCRIPTION"
    PROVIDER_MATCH = "PROVIDER_MATCH"


class HumanDecisionAction(StrEnum):
    CONFIRM = "CONFIRM"
    MODIFY = "MODIFY"
    REPLACE = "REPLACE"
    REJECT = "REJECT"
    DEFER = "DEFER"


class LearningSignalType(StrEnum):
    DIAGNOSIS_CONFIRMED = "DIAGNOSIS_CONFIRMED"
    DIAGNOSIS_MODIFIED = "DIAGNOSIS_MODIFIED"
    DIAGNOSIS_REPLACED = "DIAGNOSIS_REPLACED"
    DIAGNOSIS_REJECTED = "DIAGNOSIS_REJECTED"
    DIAGNOSIS_DEFERRED = "DIAGNOSIS_DEFERRED"
    PRESCRIPTION_CONFIRMED = "PRESCRIPTION_CONFIRMED"
    PRESCRIPTION_MODIFIED = "PRESCRIPTION_MODIFIED"
    PRESCRIPTION_REPLACED = "PRESCRIPTION_REPLACED"
    PRESCRIPTION_DEFERRED = "PRESCRIPTION_DEFERRED"
    PROVIDER_SELECTED = "PROVIDER_SELECTED"


class LearningSignalQuality(StrEnum):
    RAW = "RAW"
    CURATED = "CURATED"
    EXCLUDED = "EXCLUDED"


_TERMINAL_DIAGNOSIS_STATUSES = {
    DiagnosisStatus.CONFIRMED,
    DiagnosisStatus.MODIFIED,
    DiagnosisStatus.REPLACED,
    DiagnosisStatus.REJECTED,
}


@dataclass(frozen=True, slots=True)
class AIExecutionResult:
    provider_code: str
    model_id: str
    model_alias: str
    routing_policy_id: UUID
    routing_policy_version: str
    prompt_policy_version: str
    output_schema_version: str
    output: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class AIDecision:
    id: UUID
    household_id: UUID
    assessment_id: UUID
    feature_package_id: UUID
    pgor_snapshot_id: UUID
    decision_type: AIDecisionType
    status: AIDecisionStatus
    provider_code: str
    model_id: str
    model_alias: str
    routing_policy_id: UUID
    routing_policy_version: str
    prompt_policy_version: str
    output_schema_version: str
    structured_output: dict[str, JsonValue]
    trace_id: UUID
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class Diagnosis:
    id: UUID
    household_id: UUID
    ai_decision_id: UUID
    status: DiagnosisStatus
    version: int
    accepted_payload: dict[str, JsonValue] | None
    created_at: datetime
    latest_human_decision_id: UUID | None = None
    reviewed_at: datetime | None = None
    reviewed_by: UUID | None = None

    def review(
        self,
        *,
        action: HumanDecisionAction,
        accepted_payload: dict[str, JsonValue] | None,
        human_decision_id: UUID,
        actor_id: UUID,
        decided_at: datetime,
    ) -> "Diagnosis":
        if self.status in _TERMINAL_DIAGNOSIS_STATUSES:
            raise ValueError("Diagnosis already has a terminal human decision.")

        status_map = {
            HumanDecisionAction.CONFIRM: DiagnosisStatus.CONFIRMED,
            HumanDecisionAction.MODIFY: DiagnosisStatus.MODIFIED,
            HumanDecisionAction.REPLACE: DiagnosisStatus.REPLACED,
            HumanDecisionAction.REJECT: DiagnosisStatus.REJECTED,
            HumanDecisionAction.DEFER: DiagnosisStatus.DEFERRED,
        }
        return replace(
            self,
            status=status_map[action],
            version=self.version + 1,
            accepted_payload=accepted_payload,
            latest_human_decision_id=human_decision_id,
            reviewed_at=decided_at,
            reviewed_by=actor_id,
        )


@dataclass(frozen=True, slots=True)
class HumanDecision:
    id: UUID
    household_id: UUID
    ai_decision_id: UUID | None
    actor_id: UUID
    action: HumanDecisionAction
    reason_code: str | None
    reason_text: str | None
    accepted_payload: dict[str, JsonValue] | None
    modified_payload: dict[str, JsonValue] | None
    decided_at: datetime
    decision_context: HumanDecisionContext = HumanDecisionContext.DIAGNOSIS
    diagnosis_id: UUID | None = None
    prescription_id: UUID | None = None
    provider_match_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    id: UUID
    household_id: UUID
    trace_type: AIDecisionType
    state_fingerprint: str
    pgor_snapshot_id: UUID
    feature_package_id: UUID
    ai_decision_id: UUID
    opened_at: datetime
    human_decision_id: UUID | None = None
    closed_at: datetime | None = None
    prescription_id: UUID | None = None
    intervention_id: UUID | None = None
    provider_match_id: UUID | None = None
    provider_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class LearningSignal:
    id: UUID
    household_id: UUID
    signal_type: LearningSignalType
    ai_decision_id: UUID | None
    human_decision_id: UUID
    diagnosis_id: UUID | None
    signal_label: str
    quality_status: LearningSignalQuality
    created_at: datetime
    created_by: UUID
    prescription_id: UUID | None = None
    intervention_id: UUID | None = None
