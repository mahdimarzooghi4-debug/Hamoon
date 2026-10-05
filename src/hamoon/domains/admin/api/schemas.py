from datetime import datetime

from pydantic import BaseModel


class DataHealthData(BaseModel):
    missing_required_data: int
    unresolved_conflicts: int
    incomplete_assessments: int
    stale_source_data: int
    integration_failures: int
    pending_validation_facts: int
    disputed_facts: int
    overdue_work_items: int
    pending_outbox_messages: int
    quarantined_evidence: int
    generated_at: datetime


class DataHealthResponse(BaseModel):
    data: DataHealthData


class MachineHealthData(BaseModel):
    diagnosis_confirm_total: int
    diagnosis_modify_total: int
    diagnosis_replace_total: int
    schema_failures: int
    ai_fallback_total: int
    inference_failures: int
    workflow_backlog: int
    routing_failures: int
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
