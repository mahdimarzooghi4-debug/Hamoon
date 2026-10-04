import { requestJson } from "./client";

export type DiagnosisStatus =
  | "UNDER_REVIEW"
  | "CONFIRMED"
  | "MODIFIED"
  | "REPLACED"
  | "REJECTED"
  | "DEFERRED";

export type DiagnosisCategory = "NEED" | "RISK" | "CAPACITY" | "CONSTRAINT";
export type DiagnosisUncertainty = "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
export type HumanDecisionAction =
  | "CONFIRM"
  | "MODIFY"
  | "REPLACE"
  | "REJECT"
  | "DEFER";

export interface DiagnosisItem {
  code: string;
  category: DiagnosisCategory;
  title: string;
  rationale: string;
  supporting_feature_refs: string[];
  uncertainty: DiagnosisUncertainty;
}

export interface DiagnosisProposal {
  schema_version: "diagnosis-v1";
  summary: string;
  items: DiagnosisItem[];
  review_flags: string[];
}

export interface DiagnosisHumanDecision {
  id: string;
  actor_id: string;
  action: HumanDecisionAction;
  reason_code: string | null;
  reason_text: string | null;
  accepted_payload: DiagnosisProposal | null;
  modified_payload: DiagnosisProposal | null;
  decided_at: string;
}

export interface DiagnosisHistoryEntry {
  id: string;
  household_id: string;
  ai_decision_id: string;
  status: DiagnosisStatus;
  version: number;
  machine_proposal: DiagnosisProposal;
  accepted_payload: DiagnosisProposal | null;
  model_alias: string;
  output_schema_version: string;
  generated_at: string;
  created_at: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
  human_decisions: DiagnosisHumanDecision[];
}

interface DiagnosisHistoryResponse {
  data: DiagnosisHistoryEntry[];
}

interface GenerateDiagnosisResponse {
  data: {
    diagnosis_id: string;
    ai_decision_id: string;
    status: DiagnosisStatus;
    version: number;
    trace_id: string;
  };
}

interface ReviewDiagnosisResponse {
  data: {
    diagnosis_id: string;
    ai_decision_id: string;
    human_decision_id: string;
    learning_signal_id: string;
    action: HumanDecisionAction;
    status: DiagnosisStatus;
    version: number;
    accepted_payload: DiagnosisProposal | null;
  };
}

export async function listDiagnoses(
  householdId: string,
  limit = 50,
): Promise<DiagnosisHistoryEntry[]> {
  const response = await requestJson<DiagnosisHistoryResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/diagnoses?limit=${limit}`,
  );
  return response.data;
}

export async function generateDiagnosis(
  householdId: string,
  pgorSnapshotId: string,
): Promise<GenerateDiagnosisResponse["data"]> {
  const response = await requestJson<GenerateDiagnosisResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/diagnoses/generate`,
    {
      method: "POST",
      body: JSON.stringify({ pgor_snapshot_id: pgorSnapshotId }),
    },
  );
  return response.data;
}

export async function reviewDiagnosis(
  diagnosis: DiagnosisHistoryEntry,
  action: HumanDecisionAction,
  options: {
    reasonCode: string | null;
    reasonText: string | null;
    modifiedPayload?: DiagnosisProposal;
  },
): Promise<ReviewDiagnosisResponse["data"]> {
  const endpoint = action.toLowerCase();
  const body: Record<string, unknown> = {
    expected_version: diagnosis.version,
    reason_code: options.reasonCode,
    reason_text: options.reasonText,
  };
  if (action === "MODIFY" || action === "REPLACE") {
    body.modified_payload = options.modifiedPayload;
  }
  const response = await requestJson<ReviewDiagnosisResponse>(
    `/api/v1/diagnoses/${encodeURIComponent(diagnosis.id)}/${endpoint}`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
  return response.data;
}
