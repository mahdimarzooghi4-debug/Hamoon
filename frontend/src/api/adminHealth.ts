import { requestJson } from "./client";

export interface DataHealth {
  missing_required_data: number;
  unresolved_conflicts: number;
  incomplete_assessments: number;
  stale_source_data: number;
  integration_failures: number;
  pending_validation_facts: number;
  disputed_facts: number;
  overdue_work_items: number;
  pending_outbox_messages: number;
  quarantined_evidence: number;
  generated_at: string;
}

export interface MachineHealth {
  diagnosis_confirm_total: number;
  diagnosis_modify_total: number;
  diagnosis_replace_total: number;
  schema_failures: number;
  ai_fallback_total: number;
  inference_failures: number;
  workflow_backlog: number;
  routing_failures: number;
  ai_decisions_total: number;
  human_confirm_total: number;
  human_modify_total: number;
  human_replace_total: number;
  human_reject_total: number;
  human_defer_total: number;
  learning_signal_raw: number;
  learning_signal_curated: number;
  learning_signal_excluded: number;
  evaluation_pending: number;
  evaluation_passed: number;
  evaluation_failed: number;
  active_routing_policies: number;
  incomplete_reassessment_plans: number;
  generated_at: string;
}

interface DataHealthResponse {
  data: DataHealth;
}

interface MachineHealthResponse {
  data: MachineHealth;
}

export async function getDataHealth(): Promise<DataHealth> {
  const response = await requestJson<DataHealthResponse>(
    "/api/v1/admin/health/data",
  );
  return response.data;
}

export async function getMachineHealth(): Promise<MachineHealth> {
  const response = await requestJson<MachineHealthResponse>(
    "/api/v1/admin/health/machine",
  );
  return response.data;
}
