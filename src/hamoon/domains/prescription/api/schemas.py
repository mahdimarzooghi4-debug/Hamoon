from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, JsonValue

from hamoon.domains.prescription.domain.entities import PrescriptionStatus


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
