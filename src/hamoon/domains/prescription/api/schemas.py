from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, JsonValue

from hamoon.domains.intelligence.domain.decisions import HumanDecisionAction
from hamoon.domains.prescription.domain.entities import (
    PrescriptionItemStatus,
    PrescriptionStatus,
)


class GeneratePrescriptionRequest(BaseModel):
    diagnosis_id: UUID
    pgor_snapshot_id: UUID


class GeneratePrescriptionData(BaseModel):
    prescription_id: UUID
    ai_decision_id: UUID
    status: PrescriptionStatus
    version: int
    trace_id: UUID


class GeneratePrescriptionResponse(BaseModel):
    data: GeneratePrescriptionData


class PrescriptionData(BaseModel):
    id: UUID
    household_id: UUID
    diagnosis_id: UUID
    ai_decision_id: UUID
    pgor_snapshot_id: UUID
    status: PrescriptionStatus
    version: int
    machine_proposal: dict[str, JsonValue]
    accepted_payload: dict[str, JsonValue] | None
    created_at: datetime
    created_by: UUID


class PrescriptionResponse(BaseModel):
    data: PrescriptionData



class PrescriptionItemData(BaseModel):
    id: UUID
    source_code: str
    intervention_type: str
    target_pgor_variable: str
    priority: int
    success_criteria: list[str]
    review_after_days: int
    review_rationale: str
    rationale: str
    title: str
    status: PrescriptionItemStatus
    machine_proposed: bool


class PrescriptionReviewRequest(BaseModel):
    expected_version: int
    reason_code: str | None = None
    reason_text: str | None = None


class StructuredPrescriptionReviewRequest(PrescriptionReviewRequest):
    modified_payload: dict[str, JsonValue]


class PrescriptionReviewData(BaseModel):
    prescription_id: UUID
    ai_decision_id: UUID
    human_decision_id: UUID
    learning_signal_id: UUID
    action: HumanDecisionAction
    status: PrescriptionStatus
    version: int
    accepted_payload: dict[str, JsonValue] | None
    accepted_items: list[PrescriptionItemData]


class PrescriptionReviewResponse(BaseModel):
    data: PrescriptionReviewData
