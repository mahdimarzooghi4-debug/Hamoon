from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from hamoon.domains.intelligence.domain.decisions import (
    DiagnosisStatus,
    HumanDecisionAction,
)


class GenerateDiagnosisRequest(BaseModel):
    pgor_snapshot_id: UUID


class GenerateDiagnosisData(BaseModel):
    diagnosis_id: UUID
    ai_decision_id: UUID
    status: DiagnosisStatus
    version: int
    trace_id: UUID


class GenerateDiagnosisResponse(BaseModel):
    data: GenerateDiagnosisData


class DiagnosisData(BaseModel):
    id: UUID
    household_id: UUID
    ai_decision_id: UUID
    status: DiagnosisStatus
    version: int
    machine_proposal: dict[str, JsonValue]
    accepted_payload: dict[str, JsonValue] | None
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by: UUID | None


class DiagnosisResponse(BaseModel):
    data: DiagnosisData


class ConfirmDiagnosisRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason_code: str | None = Field(default=None, max_length=100)
    reason_text: str | None = Field(default=None, max_length=1000)


class StructuredDiagnosisReviewRequest(ConfirmDiagnosisRequest):
    modified_payload: dict[str, JsonValue]


class ReviewDiagnosisData(BaseModel):
    diagnosis_id: UUID
    ai_decision_id: UUID
    human_decision_id: UUID
    learning_signal_id: UUID
    action: HumanDecisionAction
    status: DiagnosisStatus
    version: int
    accepted_payload: dict[str, JsonValue] | None


class ReviewDiagnosisResponse(BaseModel):
    data: ReviewDiagnosisData
