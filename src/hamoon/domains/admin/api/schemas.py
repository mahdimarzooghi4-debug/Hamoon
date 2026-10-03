from datetime import datetime

from pydantic import BaseModel


class DataHealthData(BaseModel):
    pending_validation_facts: int
    disputed_facts: int
    incomplete_assessments: int
    overdue_work_items: int
    pending_outbox_messages: int
    quarantined_evidence: int
    generated_at: datetime


class DataHealthResponse(BaseModel):
    data: DataHealthData


class MachineHealthData(BaseModel):
    ai_decisions_total: int
    human_confirm_total: int
    human_modify_total: int
    human_replace_total: int
    human_reject_total: int
    human_defer_total: int
    learning_signal_raw: int
    learning_signal_curated: int
    learning_signal_excluded: int
    evaluation_pending: int
    evaluation_passed: int
    evaluation_failed: int
    active_routing_policies: int
    incomplete_reassessment_plans: int
    generated_at: datetime


class MachineHealthResponse(BaseModel):
    data: MachineHealthData
