import { requestJson } from "./client";
import type { WorkItemStatus, WorkItemType } from "./operations";

export type HouseholdStatus = "DRAFT" | "ACTIVE" | "PAUSED" | "CLOSED" | "ARCHIVED";
export type PGORVariable = "P" | "G" | "O" | "R";
export type EBand =
  | "SEVERE_CRISIS"
  | "VULNERABLE"
  | "SUPPORTED_EMPOWERMENT"
  | "ECONOMIC_SOCIAL_INDEPENDENCE";

type DecimalValue = string | number;

export interface HouseholdPGOR {
  snapshot_id: string;
  assessment_id: string;
  calculated_at: string;
  p: DecimalValue;
  g: DecimalValue;
  o: DecimalValue;
  r: DecimalValue;
  e: DecimalValue;
  e_band: EBand;
  bottleneck_variables: PGORVariable[];
  data_quality_flags: string[];
}

export interface HouseholdIntervention {
  id: string;
  intervention_type: string;
  target_pgor_variable: PGORVariable;
  status: "PLANNED" | "READY_FOR_REFERRAL" | "REFERRED" | "ACTIVE" | "COMPLETED" | "CANCELLED";
}

export interface HouseholdNextWorkItem {
  id: string;
  work_type: WorkItemType;
  title: string;
  reason: string;
  priority: number;
  status: WorkItemStatus;
  due_at: string | null;
  version: number;
}

export interface HouseholdSummary {
  id: string;
  case_code: string;
  lifecycle_status: HouseholdStatus;
  organizational_unit_id: string | null;
  primary_caseworker_id: string | null;
  version: number;
  pgor: HouseholdPGOR | null;
  current_intervention: HouseholdIntervention | null;
  next_work_item: HouseholdNextWorkItem | null;
}

interface HouseholdListResponse {
  data: HouseholdSummary[];
}

interface HouseholdDetailResponse {
  data: HouseholdSummary;
}

export async function getHouseholds(query = ""): Promise<HouseholdSummary[]> {
  const params = new URLSearchParams({ limit: "100" });
  if (query.trim().length > 0) {
    params.set("q", query.trim());
  }
  const response = await requestJson<HouseholdListResponse>(
    `/api/v1/households?${params.toString()}`,
  );
  return response.data;
}

export async function getHousehold(householdId: string): Promise<HouseholdSummary> {
  const response = await requestJson<HouseholdDetailResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}`,
  );
  return response.data;
}


export type HouseholdTimelineKind =
  | "FACT"
  | "ASSESSMENT"
  | "PGOR"
  | "DIAGNOSIS"
  | "PRESCRIPTION"
  | "REFERRAL"
  | "PROVIDER_RESULT"
  | "OUTCOME";

export interface HouseholdTimelineItem {
  kind: HouseholdTimelineKind;
  entity_id: string;
  occurred_at: string;
  status: string;
  detail: string | null;
}

interface HouseholdTimelineResponse {
  data: HouseholdTimelineItem[];
}

export async function getHouseholdTimeline(
  householdId: string,
): Promise<HouseholdTimelineItem[]> {
  const response = await requestJson<HouseholdTimelineResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/timeline?limit=200`,
  );
  return response.data;
}
