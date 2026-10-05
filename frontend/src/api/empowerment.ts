import { requestJson } from "./client";

export type EBand =
  | "SEVERE_CRISIS"
  | "VULNERABLE"
  | "SUPPORTED_EMPOWERMENT"
  | "ECONOMIC_SOCIAL_INDEPENDENCE";

export type PGORVariable = "P" | "G" | "O" | "R";

export type OutcomeClassification =
  | "GOAL_ACHIEVED"
  | "PROGRESS"
  | "NO_SIGNIFICANT_CHANGE"
  | "REGRESSION"
  | "NEEDS_MORE_TIME"
  | "NEEDS_MORE_DATA";

export interface PGORDistribution {
  mean: string | number | null;
  minimum: string | number | null;
  maximum: string | number | null;
}

export interface EmpowermentOverview {
  scope_unit_id: string;
  household_count: number;
  households_with_official_pgor: number;
  p: PGORDistribution;
  g: PGORDistribution;
  o: PGORDistribution;
  r: PGORDistribution;
  e: PGORDistribution;
  e_band_counts: Record<EBand, number>;
  bottleneck_counts: Record<PGORVariable, number>;
  outcome_counts: Record<OutcomeClassification, number>;
  unreviewed_outcomes: number;
  generated_at: string;
}

interface EmpowermentOverviewResponse {
  data: EmpowermentOverview;
}

export async function getEmpowermentOverview(): Promise<EmpowermentOverview> {
  const response = await requestJson<EmpowermentOverviewResponse>(
    "/api/v1/admin/empowerment/overview",
  );
  return response.data;
}
