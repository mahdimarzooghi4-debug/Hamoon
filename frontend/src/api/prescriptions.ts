import { requestJson } from "./client";
import type { HumanDecisionAction } from "./diagnosis";
import type { PGORVariable } from "./households";

export type PrescriptionStatus =
  | "UNDER_REVIEW"
  | "APPROVED"
  | "MODIFIED"
  | "REPLACED"
  | "DEFERRED";

export type PrescriptionItemStatus = "ACCEPTED" | "ACTIVATED" | "SUPERSEDED";

export type InterventionType =
  | "COUNSELING"
  | "MOTIVATION"
  | "PSYCHOLOGICAL_EMPOWERMENT"
  | "COACHING"
  | "TRAINING"
  | "SKILLS_TRAINING"
  | "VOCATIONAL_TRAINING"
  | "MARKET_LINKAGE"
  | "EMPLOYMENT"
  | "FINANCING_FACILITIES"
  | "NETWORKING"
  | "SOCIAL_SUPPORT"
  | "TREATMENT"
  | "RISK_REDUCTION"
  | "STABILIZATION";

export interface PrescriptionProposalItem {
  code: string;
  target_variable: PGORVariable;
  intervention_type: InterventionType;
  priority_rank: number;
  title: string;
  rationale: string;
  success_criteria: string[];
  review_schedule: {
    review_after_days: number;
    rationale: string;
  };
  diagnosis_refs: string[];
  supporting_feature_refs: string[];
}

export interface PrescriptionProposal {
  schema_version: "prescription-v1";
  summary: string;
  intensity_score: string;
  items: PrescriptionProposalItem[];
  review_flags: string[];
}

export interface PrescriptionHumanDecision {
  id: string;
  actor_id: string;
  action: HumanDecisionAction;
  reason_code: string | null;
  reason_text: string | null;
  accepted_payload: PrescriptionProposal | null;
  modified_payload: PrescriptionProposal | null;
  decided_at: string;
}

export interface AcceptedPrescriptionItem {
  id: string;
  source_code: string;
  intervention_type: InterventionType;
  target_pgor_variable: PGORVariable;
  priority: number;
  success_criteria: string[];
  review_after_days: number;
  review_rationale: string;
  rationale: string;
  title: string;
  status: PrescriptionItemStatus;
  machine_proposed: boolean;
}

export interface PrescriptionHistoryEntry {
  id: string;
  household_id: string;
  diagnosis_id: string;
  ai_decision_id: string;
  pgor_snapshot_id: string;
  status: PrescriptionStatus;
  version: number;
  machine_proposal: PrescriptionProposal;
  accepted_payload: PrescriptionProposal | null;
  model_alias: string;
  output_schema_version: string;
  generated_at: string;
  created_at: string;
  created_by: string;
  accepted_at: string | null;
  accepted_by: string | null;
  human_decisions: PrescriptionHumanDecision[];
  accepted_items: AcceptedPrescriptionItem[];
}

interface PrescriptionHistoryResponse {
  data: PrescriptionHistoryEntry[];
}

interface GeneratePrescriptionResponse {
  data: {
    prescription_id: string;
    ai_decision_id: string;
    status: PrescriptionStatus;
    version: number;
    trace_id: string;
  };
}

interface PrescriptionReviewResponse {
  data: {
    prescription_id: string;
    ai_decision_id: string;
    human_decision_id: string;
    learning_signal_id: string;
    action: HumanDecisionAction;
    status: PrescriptionStatus;
    version: number;
    accepted_payload: PrescriptionProposal | null;
    accepted_items: AcceptedPrescriptionItem[];
  };
}

export interface Intervention {
  id: string;
  household_id: string;
  prescription_item_id: string;
  intervention_type: InterventionType;
  target_pgor_variable: PGORVariable;
  status:
    | "PLANNED"
    | "READY_FOR_REFERRAL"
    | "REFERRED"
    | "ACTIVE"
    | "COMPLETED"
    | "CANCELLED";
  started_at: string | null;
  completed_at: string | null;
  owner_actor_id: string | null;
}

interface InterventionResponse {
  data: Intervention;
}

export async function listPrescriptions(
  householdId: string,
  limit = 50,
): Promise<PrescriptionHistoryEntry[]> {
  const response = await requestJson<PrescriptionHistoryResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/prescriptions?limit=${limit}`,
  );
  return response.data;
}

export async function generatePrescription(
  householdId: string,
  diagnosisId: string,
  pgorSnapshotId: string,
): Promise<GeneratePrescriptionResponse["data"]> {
  const response = await requestJson<GeneratePrescriptionResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/prescriptions/generate`,
    {
      method: "POST",
      body: JSON.stringify({
        diagnosis_id: diagnosisId,
        pgor_snapshot_id: pgorSnapshotId,
      }),
    },
  );
  return response.data;
}

export async function reviewPrescription(
  prescription: PrescriptionHistoryEntry,
  action: Extract<HumanDecisionAction, "CONFIRM" | "MODIFY" | "REPLACE" | "DEFER">,
  options: {
    reasonCode: string | null;
    reasonText: string | null;
    modifiedPayload?: PrescriptionProposal;
  },
): Promise<PrescriptionReviewResponse["data"]> {
  const endpoint = {
    CONFIRM: "approve",
    MODIFY: "modify",
    REPLACE: "replace",
    DEFER: "defer",
  }[action];

  const body: Record<string, unknown> = {
    expected_version: prescription.version,
    reason_code: options.reasonCode,
    reason_text: options.reasonText,
  };
  if (action === "MODIFY" || action === "REPLACE") {
    body.modified_payload = options.modifiedPayload;
  }

  const response = await requestJson<PrescriptionReviewResponse>(
    `/api/v1/prescriptions/${encodeURIComponent(prescription.id)}/${endpoint}`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
  return response.data;
}

export async function activatePrescriptionItem(
  prescriptionId: string,
  itemId: string,
): Promise<Intervention> {
  const response = await requestJson<InterventionResponse>(
    `/api/v1/prescriptions/${encodeURIComponent(prescriptionId)}/items/${encodeURIComponent(itemId)}/activate`,
    { method: "POST" },
  );
  return response.data;
}
