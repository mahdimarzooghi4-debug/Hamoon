from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from hamoon.domains.outcome.domain.entities import (
    OutcomeClassification,
    OutcomeStatus,
)


class PrepareOutcomeRequest(BaseModel):
    pre_assessment_id: UUID
    post_assessment_id: UUID
    provider_result_id: UUID


class ReviewOutcomeRequest(BaseModel):
    expected_version: int = Field(ge=1)
    classification: OutcomeClassification
    observed_change_summary: str | None = Field(default=None, max_length=4000)
    reason_code: str | None = Field(default=None, max_length=100)
    reason_text: str | None = Field(default=None, max_length=1000)


class DeferOutcomeRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason_code: str | None = Field(default=None, max_length=100)
    reason_text: str | None = Field(default=None, max_length=1000)


class OutcomeData(BaseModel):
    id: UUID
    household_id: UUID
    intervention_id: UUID
    referral_id: UUID | None
    provider_result_id: UUID | None
    pre_assessment_id: UUID
    post_assessment_id: UUID
    pre_pgor_snapshot_id: UUID
    post_pgor_snapshot_id: UUID
    status: OutcomeStatus
    classification: OutcomeClassification | None
    observed_change_summary: str
    p_delta: Decimal
    g_delta: Decimal
    o_delta: Decimal
    r_delta: Decimal
    e_delta: Decimal
    confidence: Decimal | None
    methodology_version: str
    version: int
    assessed_at: datetime
    latest_human_decision_id: UUID | None
    learning_signal_id: UUID | None = None


class OutcomeResponse(BaseModel):
    data: OutcomeData



class GenerateOutcomeInterpretationData(BaseModel):
    proposal_id: UUID
    outcome_id: UUID
    ai_decision_id: UUID
    trace_id: UUID


class GenerateOutcomeInterpretationResponse(BaseModel):
    data: GenerateOutcomeInterpretationData


class OutcomeInterpretationData(BaseModel):
    proposal_id: UUID
    outcome_id: UUID
    ai_decision_id: UUID
    feature_package_id: UUID
    trace_id: UUID
    model_alias: str
    routing_policy_version: str
    prompt_policy_version: str
    output_schema_version: str
    machine_proposal: dict[str, JsonValue]
    created_at: datetime


class OutcomeInterpretationResponse(BaseModel):
    data: OutcomeInterpretationData
