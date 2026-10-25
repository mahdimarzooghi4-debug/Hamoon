import { requestJson } from "./client";

export type FactValueType = "STRING" | "NUMBER" | "BOOLEAN" | "DATE" | "DATETIME" | "CODE" | "RANGE" | "JSON_STRUCTURED";
export type ValidationStatus = "PENDING_VALIDATION" | "VALIDATED" | "DISPUTED" | "REJECTED" | "SUPERSEDED";
export type SourceType = "HOUSEHOLD_DECLARATION" | "EXPERT_ASSESSMENT" | "EXTERNAL_DATA";

export interface DataSource {
  id: string;
  code: string;
  name: string;
  source_type: SourceType;
}

export interface HouseholdFact {
  id: string;
  household_id: string;
  fact_type: string;
  value_type: FactValueType;
  value: unknown;
  source_id: string;
  source_detail: string | null;
  effective_from: string;
  recorded_at: string;
  version: number;
  validation_status: ValidationStatus;
  validation_version: number;
}

export interface AcceptedFact {
  household_id: string;
  fact_type: string;
  fact_id: string;
  accepted_value: unknown;
  source_id: string;
  effective_from: string;
  projection_version: number;
  projected_at: string;
}

function householdPath(householdId: string): string {
  return "/api/v1/households/" + encodeURIComponent(householdId);
}

export async function getDataSources(): Promise<DataSource[]> {
  const response = await requestJson<{ data: DataSource[] }>("/api/v1/data-sources");
  return response.data;
}

export async function getHouseholdFacts(householdId: string): Promise<HouseholdFact[]> {
  const response = await requestJson<{ data: HouseholdFact[] }>(householdPath(householdId) + "/facts");
  return response.data;
}

export async function getAcceptedFacts(householdId: string): Promise<AcceptedFact[]> {
  const response = await requestJson<{ data: AcceptedFact[] }>(householdPath(householdId) + "/accepted-state");
  return response.data;
}

export async function recordHouseholdFact(
  householdId: string,
  input: {
    fact_type: string;
    value_type: FactValueType;
    value: unknown;
    source_id: string;
    source_detail: string | null;
    effective_from: string;
  },
): Promise<HouseholdFact> {
  const response = await requestJson<{ data: HouseholdFact }>(householdPath(householdId) + "/facts", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return response.data;
}

export async function changeFactValidation(
  householdId: string,
  fact: HouseholdFact,
  toStatus: "VALIDATED" | "DISPUTED" | "REJECTED",
  reasonCode: string,
  reasonText: string,
): Promise<void> {
  await requestJson(householdPath(householdId) + "/facts/" + encodeURIComponent(fact.id) + "/validation", {
    method: "POST",
    body: JSON.stringify({
      to_status: toStatus,
      expected_validation_version: fact.validation_version,
      reason_code: reasonCode,
      reason_text: reasonText,
    }),
  });
}

export async function resolveAcceptedFact(
  householdId: string,
  fact: HouseholdFact,
  expectedProjectionVersion: number,
  reasonCode: string,
  reasonText: string,
): Promise<AcceptedFact> {
  const response = await requestJson<{ data: AcceptedFact }>(
    householdPath(householdId) + "/accepted-state/" + encodeURIComponent(fact.fact_type) + "/resolve",
    {
      method: "POST",
      body: JSON.stringify({
        fact_id: fact.id,
        expected_projection_version: expectedProjectionVersion,
        reason_code: reasonCode,
        reason_text: reasonText,
      }),
    },
  );
  return response.data;
}
