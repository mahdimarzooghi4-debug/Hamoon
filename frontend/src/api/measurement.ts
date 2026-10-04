import { ApiError, requestJson } from "./client";
import type { WorkItem } from "./operations";
import type { PGORVariable } from "./households";

export type ReassessmentPlanStatus =
  | "SCHEDULED"
  | "TASK_CREATED"
  | "REASSESSMENT_STARTED"
  | "POST_PGOR_READY"
  | "OUTCOME_REVIEW"
  | "COMPLETED"
  | "CANCELLED";

export interface ProviderResult {
  id: string;
  referral_id: string;
  provider_id: string;
  result_status: string;
  result_type: string;
  result_summary: string;
  result_payload: Record<string, unknown> | null;
  service_started_at: string | null;
  service_completed_at: string | null;
  submitted_at: string;
  external_result_id: string;
  provider_reference: string | null;
  evidence: string[];
  duplicate: boolean;
  reassessment_plan_id: string | null;
  reassessment_due_at: string | null;
  workflow_id: string | null;
  reassessment_status: ReassessmentPlanStatus | null;
}

export interface ReassessmentPlan {
  id: string;
  household_id: string;
  intervention_id: string;
  provider_result_id: string;
  prescription_item_id: string;
  assigned_actor_id: string;
  review_after_days: number;
  due_at: string;
  policy_version: string;
  workflow_id: string;
  status: ReassessmentPlanStatus;
  version: number;
  created_at: string;
  work_item_id: string | null;
  task_created_at: string | null;
  post_assessment_id: string | null;
  post_pgor_snapshot_id: string | null;
  outcome_id: string | null;
  outcome_work_item_id: string | null;
}

export type ObservationValidationStatus =
  | "PENDING_VALIDATION"
  | "VALIDATED"
  | "DISPUTED"
  | "REJECTED"
  | "SUPERSEDED";

export interface AssessmentWorkspaceObservation {
  id: string;
  raw_score_0_100: string | number;
  source_id: string;
  source_detail: string | null;
  effective_at: string;
  observed_at: string;
  validation_status: ObservationValidationStatus | null;
  validation_version: number | null;
  accepted: boolean;
  accepted_projection_version: number | null;
}

export interface AssessmentWorkspaceIndicator {
  id: string;
  variable_code: PGORVariable;
  variable_name_fa: string;
  dimension_code: string;
  dimension_name_fa: string;
  code: string;
  name_fa: string;
  score_min: number;
  score_max: number;
  required_for_complete_assessment: boolean | null;
  direct_dimension_measure: boolean;
  latest_observation: AssessmentWorkspaceObservation | null;
}

export interface AssessmentData {
  id: string;
  household_id: string;
  assessment_type: "BASELINE" | "REASSESSMENT" | "OUTCOME_REASSESSMENT";
  definition_version_id: string;
  status:
    | "DRAFT"
    | "IN_PROGRESS"
    | "READY_FOR_CALCULATION"
    | "COMPLETED"
    | "CANCELLED";
  version: number;
  started_at: string;
  reason: string | null;
  intervention_id: string | null;
  provider_result_id: string | null;
  parent_assessment_id: string | null;
}

export interface AssessmentWorkspace {
  assessment: AssessmentData;
  definition_code: string;
  definition_version: string;
  indicators: AssessmentWorkspaceIndicator[];
}

export interface AssessmentReadiness {
  assessment_id: string;
  status: "REQUIREMENT_POLICY_UNRESOLVED" | "INCOMPLETE" | "READY";
  total_indicator_count: number;
  accepted_indicator_count: number;
  required_indicator_count: number | null;
  accepted_required_indicator_count: number | null;
  completeness_ratio: string | number | null;
  missing_required_indicator_ids: string[];
  unresolved_validation_count: number;
  blocking_reasons: string[];
  accepted_observation_ids: string[];
}

export interface DataSource {
  id: string;
  code: string;
  source_type:
    | "HOUSEHOLD_DECLARATION"
    | "EXPERT_ASSESSMENT"
    | "EXTERNAL_DATA";
  name: string;
}

export interface PGORSnapshot {
  id: string;
  household_id: string;
  assessment_id: string;
  definition_version_id: string;
  formula_version_id: string;
  engine_version: string;
  scoring_version: string;
  status: "OFFICIAL";
  p: string | number;
  g: string | number;
  o: string | number;
  r: string | number;
  e: string | number;
  bottleneck_variables: PGORVariable[];
  e_band: string;
  p_band: string;
  r_band: string;
  completeness_ratio: string | number | null;
  data_quality_flags: string[];
  input_fingerprint: string;
}

export type OutcomeClassification =
  | "GOAL_ACHIEVED"
  | "PROGRESS"
  | "NO_SIGNIFICANT_CHANGE"
  | "REGRESSION"
  | "NEEDS_MORE_TIME"
  | "NEEDS_MORE_DATA";

export type OutcomeStatus =
  | "UNDER_REVIEW"
  | "CONFIRMED"
  | "MODIFIED"
  | "NEEDS_MORE_TIME"
  | "NEEDS_MORE_DATA";

export interface Outcome {
  id: string;
  household_id: string;
  intervention_id: string;
  referral_id: string | null;
  provider_result_id: string | null;
  pre_assessment_id: string;
  post_assessment_id: string;
  pre_pgor_snapshot_id: string;
  post_pgor_snapshot_id: string;
  status: OutcomeStatus;
  classification: OutcomeClassification | null;
  observed_change_summary: string;
  p_delta: string | number;
  g_delta: string | number;
  o_delta: string | number;
  r_delta: string | number;
  e_delta: string | number;
  confidence: string | number | null;
  methodology_version: string;
  version: number;
  assessed_at: string;
  latest_human_decision_id: string | null;
  learning_signal_id: string | null;
}

export interface OutcomeInterpretation {
  proposal_id: string;
  outcome_id: string;
  ai_decision_id: string;
  feature_package_id: string;
  trace_id: string;
  model_alias: string;
  routing_policy_version: string;
  prompt_policy_version: string;
  output_schema_version: string;
  machine_proposal: Record<string, unknown>;
  created_at: string;
}

interface ProviderResultListResponse {
  data: ProviderResult[];
}
interface ReassessmentPlanResponse {
  data: ReassessmentPlan;
}
interface StartReassessmentResponse {
  data: {
    work_item: WorkItem;
    assessment_id: string;
    reassessment_plan_id: string;
    definition_version_id: string;
    parent_assessment_id: string | null;
  };
}
interface AssessmentWorkspaceResponse {
  data: AssessmentWorkspace;
}
interface AssessmentReadinessResponse {
  data: AssessmentReadiness;
}
interface DataSourceListResponse {
  data: DataSource[];
}
interface ObservationResponse {
  data: AssessmentWorkspaceObservation & {
    assessment_id: string;
    indicator_definition_id: string;
  };
}
interface ValidationResponse {
  data: {
    observation_id: string;
    status: ObservationValidationStatus;
    version: number;
    changed_at: string;
    reason_code: string;
    reason_text: string | null;
  };
}
interface AcceptedObservationResponse {
  data: {
    assessment_id: string;
    indicator_definition_id: string;
    observation_id: string;
    projection_version: number;
    changed_at: string;
  };
}
interface PGORSnapshotResponse {
  data: PGORSnapshot;
}
interface OutcomeResponse {
  data: Outcome;
}
interface OutcomeInterpretationResponse {
  data: OutcomeInterpretation;
}

export async function listProviderResults(referralId: string): Promise<ProviderResult[]> {
  const response = await requestJson<ProviderResultListResponse>(
    `/api/v1/referrals/${encodeURIComponent(referralId)}/provider-results`,
  );
  return response.data;
}

export async function getReassessmentPlan(planId: string): Promise<ReassessmentPlan> {
  const response = await requestJson<ReassessmentPlanResponse>(
    `/api/v1/reassessment-plans/${encodeURIComponent(planId)}`,
  );
  return response.data;
}

export async function startPlannedReassessment(
  item: WorkItem,
): Promise<StartReassessmentResponse["data"]> {
  const response = await requestJson<StartReassessmentResponse>(
    `/api/v1/work-queue/${encodeURIComponent(item.id)}/reassessment/start`,
    {
      method: "POST",
      body: JSON.stringify({ expected_version: item.version }),
    },
  );
  return response.data;
}

export async function getAssessmentWorkspace(
  assessmentId: string,
): Promise<AssessmentWorkspace> {
  const response = await requestJson<AssessmentWorkspaceResponse>(
    `/api/v1/assessments/${encodeURIComponent(assessmentId)}/workspace`,
  );
  return response.data;
}

export async function getAssessmentReadiness(
  assessmentId: string,
): Promise<AssessmentReadiness> {
  const response = await requestJson<AssessmentReadinessResponse>(
    `/api/v1/assessments/${encodeURIComponent(assessmentId)}/readiness`,
  );
  return response.data;
}

export async function listDataSources(): Promise<DataSource[]> {
  const response = await requestJson<DataSourceListResponse>("/api/v1/data-sources");
  return response.data;
}

export async function recordAssessmentObservation(
  assessmentId: string,
  input: {
    indicatorId: string;
    rawScore: number;
    sourceId: string;
    sourceDetail: string | null;
    effectiveAt: string;
  },
): Promise<void> {
  await requestJson<ObservationResponse>(
    `/api/v1/assessments/${encodeURIComponent(assessmentId)}/observations`,
    {
      method: "POST",
      body: JSON.stringify({
        indicator_definition_id: input.indicatorId,
        raw_score_0_100: input.rawScore,
        source_id: input.sourceId,
        source_detail: input.sourceDetail,
        effective_at: input.effectiveAt,
      }),
    },
  );
}

export async function changeAssessmentObservationValidation(
  assessmentId: string,
  observation: AssessmentWorkspaceObservation,
  toStatus: Extract<
    ObservationValidationStatus,
    "VALIDATED" | "DISPUTED" | "REJECTED"
  >,
): Promise<void> {
  if (observation.validation_version === null) {
    throw new Error("Observation validation version is missing.");
  }
  const reasonCode = {
    VALIDATED: "CASEWORKER_REASSESSMENT_VALIDATED",
    DISPUTED: "CASEWORKER_REASSESSMENT_DISPUTED",
    REJECTED: "CASEWORKER_REASSESSMENT_REJECTED",
  }[toStatus];
  await requestJson<ValidationResponse>(
    `/api/v1/assessments/${encodeURIComponent(assessmentId)}/observations/${encodeURIComponent(observation.id)}/validation`,
    {
      method: "POST",
      body: JSON.stringify({
        to_status: toStatus,
        expected_validation_version: observation.validation_version,
        reason_code: reasonCode,
        reason_text: null,
      }),
    },
  );
}

export async function acceptAssessmentObservation(
  assessmentId: string,
  indicatorId: string,
  observation: AssessmentWorkspaceObservation,
): Promise<void> {
  await requestJson<AcceptedObservationResponse>(
    `/api/v1/assessments/${encodeURIComponent(assessmentId)}/accepted-observations/${encodeURIComponent(indicatorId)}/resolve`,
    {
      method: "POST",
      body: JSON.stringify({
        observation_id: observation.id,
        expected_projection_version:
          observation.accepted_projection_version ?? 0,
        reason_code: "CASEWORKER_REASSESSMENT_ACCEPTED",
        reason_text: null,
      }),
    },
  );
}

export async function calculateOfficialPGOR(
  assessmentId: string,
): Promise<PGORSnapshot> {
  const response = await requestJson<PGORSnapshotResponse>(
    `/api/v1/assessments/${encodeURIComponent(assessmentId)}/calculate-pgor`,
    {
      method: "POST",
      body: JSON.stringify({ formula_version_id: null }),
    },
  );
  return response.data;
}

export async function getPGORSnapshot(snapshotId: string): Promise<PGORSnapshot> {
  const response = await requestJson<PGORSnapshotResponse>(
    `/api/v1/pgor/snapshots/${encodeURIComponent(snapshotId)}`,
  );
  return response.data;
}

export async function getOutcome(outcomeId: string): Promise<Outcome> {
  const response = await requestJson<OutcomeResponse>(
    `/api/v1/outcomes/${encodeURIComponent(outcomeId)}`,
  );
  return response.data;
}

export async function getOutcomeInterpretation(
  outcomeId: string,
): Promise<OutcomeInterpretation | null> {
  try {
    const response = await requestJson<OutcomeInterpretationResponse>(
      `/api/v1/outcomes/${encodeURIComponent(outcomeId)}/interpretation`,
    );
    return response.data;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function reviewOutcome(
  outcome: Outcome,
  action: "confirm" | "modify" | "needs-more-time" | "needs-more-data",
  input: {
    classification?: OutcomeClassification;
    observedChangeSummary?: string | null;
    reasonCode?: string | null;
    reasonText?: string | null;
  },
): Promise<Outcome> {
  const body =
    action === "needs-more-time" || action === "needs-more-data"
      ? {
          expected_version: outcome.version,
          reason_code: input.reasonCode ?? null,
          reason_text: input.reasonText ?? null,
        }
      : {
          expected_version: outcome.version,
          classification: input.classification,
          observed_change_summary: input.observedChangeSummary ?? null,
          reason_code: input.reasonCode ?? null,
          reason_text: input.reasonText ?? null,
        };

  const response = await requestJson<OutcomeResponse>(
    `/api/v1/outcomes/${encodeURIComponent(outcome.id)}/${action}`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
  return response.data;
}
