import { requestJson } from "./client";

export type LearningSignalQuality = "RAW" | "CURATED" | "EXCLUDED";
export type LearningSignalType =
  | "DIAGNOSIS_CONFIRMED"
  | "DIAGNOSIS_MODIFIED"
  | "DIAGNOSIS_REPLACED"
  | "DIAGNOSIS_REJECTED"
  | "DIAGNOSIS_DEFERRED"
  | "PRESCRIPTION_APPROVED"
  | "PRESCRIPTION_MODIFIED"
  | "PRESCRIPTION_REPLACED"
  | "PRESCRIPTION_DEFERRED"
  | "PROVIDER_SELECTED"
  | "OUTCOME_OBSERVED";

export interface LearningSignal {
  id: string;
  household_id: string;
  signal_type: LearningSignalType;
  ai_decision_id: string | null;
  human_decision_id: string;
  diagnosis_id: string | null;
  prescription_id: string | null;
  intervention_id: string | null;
  provider_match_id: string | null;
  provider_id: string | null;
  provider_result_id: string | null;
  outcome_id: string | null;
  signal_label: string;
  quality_status: LearningSignalQuality;
  created_at: string;
}

export type DatasetStatus = "DRAFT" | "APPROVED" | "RETIRED";

export interface LearningDataset {
  id: string;
  dataset_key: string;
  version: string;
  purpose: string;
  selection_policy_version: string;
  status: DatasetStatus;
  manifest_ref: string;
  manifest_digest: string;
  item_count: number;
  created_at: string;
  created_by: string;
  approved_at: string | null;
  approved_by: string | null;
}

export interface DatasetExport {
  dataset_id: string;
  dataset_version: string;
  status: DatasetStatus;
  manifest_digest: string;
  selection_policy_version: string;
  cases: Array<{
    case_id: string;
    input: Record<string, unknown>;
    expert_classification: string;
    source_refs: string[];
  }>;
}

export type ModelVersionStatus =
  | "EXPERIMENT"
  | "CANDIDATE"
  | "APPROVED"
  | "PRODUCTION"
  | "RETIRED";

export interface ModelVersionCatalogItem {
  id: string;
  ai_model_id: string;
  model_key: string;
  purpose: string;
  provider_id: string;
  provider_code: string;
  provider_status: "ACTIVE" | "DISABLED";
  version: string;
  concrete_model_id: string;
  artifact_ref: string | null;
  artifact_sha256: string | null;
  parent_model_version_id: string | null;
  training_dataset_version_id: string | null;
  training_dataset_manifest_digest: string | null;
  training_recipe_version: string | null;
  trained_at: string | null;
  status: ModelVersionStatus;
  limitations: string | null;
  approved_at: string | null;
  deployed_at: string | null;
}

export type PromptPolicyStatus = "DRAFT" | "APPROVED" | "ACTIVE" | "RETIRED";

export interface PromptPolicyVersionCatalogItem {
  id: string;
  prompt_policy_id: string;
  policy_name: string;
  purpose: string;
  version: string;
  output_schema_version: string;
  guardrail_version: string;
  status: PromptPolicyStatus;
  approved_at: string | null;
}

export type EvaluationStatus = "PENDING" | "RUNNING" | "PASSED" | "FAILED";

export interface EvaluationRun {
  id: string;
  task_class: string;
  model_version_id: string;
  prompt_policy_version_id: string;
  evaluation_policy_version: string;
  dataset_version_id: string | null;
  dataset_manifest_digest: string | null;
  report_digest: string | null;
  status: EvaluationStatus;
  passed: boolean;
  summary_metrics: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
}

export type RoutingPolicyStatus = "DRAFT" | "ACTIVE" | "RETIRED";

export interface RoutingPolicy {
  id: string;
  task_class: string;
  version: string;
  model_alias: string;
  model_version_id: string;
  prompt_policy_version_id: string;
  evaluation_run_id: string;
  structured_output_required: boolean;
  status: RoutingPolicyStatus;
  approved_at: string | null;
}

interface DataResponse<T> {
  data: T;
}

export async function listLearningSignals(
  limit = 500,
): Promise<LearningSignal[]> {
  const response = await requestJson<DataResponse<LearningSignal[]>>(
    `/api/v1/learning/signals?limit=${limit}`,
  );
  return response.data;
}

export async function curateLearningSignal(
  signal: LearningSignal,
  toQuality: Extract<LearningSignalQuality, "CURATED" | "EXCLUDED">,
  reasonCode: string,
): Promise<LearningSignal> {
  const response = await requestJson<DataResponse<LearningSignal>>(
    `/api/v1/admin/learning/signals/${encodeURIComponent(signal.id)}/quality`,
    {
      method: "POST",
      body: JSON.stringify({
        expected_quality_status: signal.quality_status,
        to_quality_status: toQuality,
        reason_code: reasonCode,
      }),
    },
  );
  return response.data;
}

export async function listLearningDatasets(
  limit = 100,
): Promise<LearningDataset[]> {
  const response = await requestJson<DataResponse<LearningDataset[]>>(
    `/api/v1/admin/learning/datasets?limit=${limit}`,
  );
  return response.data;
}

export async function createOutcomeDataset(input: {
  datasetKey: string;
  version: string;
  selectionPolicyVersion: string;
  signalIds: string[];
}): Promise<LearningDataset> {
  const response = await requestJson<DataResponse<LearningDataset>>(
    "/api/v1/admin/learning/datasets",
    {
      method: "POST",
      body: JSON.stringify({
        dataset_key: input.datasetKey,
        version: input.version,
        selection_policy_version: input.selectionPolicyVersion,
        signal_ids: input.signalIds,
      }),
    },
  );
  return response.data;
}

export async function approveLearningDataset(
  datasetId: string,
): Promise<LearningDataset> {
  const response = await requestJson<DataResponse<LearningDataset>>(
    `/api/v1/admin/learning/datasets/${encodeURIComponent(datasetId)}/approve`,
    { method: "POST" },
  );
  return response.data;
}

export async function exportLearningDataset(
  datasetId: string,
): Promise<DatasetExport> {
  const response = await requestJson<DataResponse<DatasetExport>>(
    `/api/v1/admin/learning/datasets/${encodeURIComponent(datasetId)}/export`,
  );
  return response.data;
}

export async function registerLocalModelCandidate(input: {
  taskClass: string;
  modelKey: string;
  version: string;
  concreteModelId: string;
  artifactRef: string;
  artifactSha256: string;
  parentModelVersionId?: string;
  trainingDataset: LearningDataset;
  trainingRecipeVersion: string;
  trainedAt: string;
  limitations?: string;
}): Promise<ModelVersionCatalogItem> {
  const response = await requestJson<DataResponse<ModelVersionCatalogItem>>(
    "/api/v1/admin/ai/model-candidates",
    {
      method: "POST",
      body: JSON.stringify({
        task_class: input.taskClass,
        model_key: input.modelKey,
        version: input.version,
        concrete_model_id: input.concreteModelId,
        artifact_ref: input.artifactRef,
        artifact_sha256: input.artifactSha256,
        parent_model_version_id: input.parentModelVersionId || null,
        training_dataset_version_id: input.trainingDataset.id,
        training_dataset_manifest_digest: input.trainingDataset.manifest_digest,
        training_recipe_version: input.trainingRecipeVersion,
        trained_at: input.trainedAt,
        limitations: input.limitations || null,
      }),
    },
  );
  return response.data;
}

export async function listModelVersions(): Promise<ModelVersionCatalogItem[]> {
  const response = await requestJson<DataResponse<ModelVersionCatalogItem[]>>(
    "/api/v1/admin/ai/model-versions",
  );
  return response.data;
}

export async function listPromptPolicyVersions(): Promise<
  PromptPolicyVersionCatalogItem[]
> {
  const response = await requestJson<
    DataResponse<PromptPolicyVersionCatalogItem[]>
  >("/api/v1/admin/ai/prompt-policy-versions");
  return response.data;
}

export async function listEvaluations(
  taskClass = "OUTCOME_INTERPRETATION",
): Promise<EvaluationRun[]> {
  const params = new URLSearchParams({
    task_class: taskClass,
    limit: "100",
  });
  const response = await requestJson<DataResponse<EvaluationRun[]>>(
    `/api/v1/admin/ai/evaluations?${params.toString()}`,
  );
  return response.data;
}

export async function createEvaluation(input: {
  modelVersionId: string;
  promptPolicyVersionId: string;
  datasetVersionId: string;
  evaluationPolicyVersion: string;
}): Promise<EvaluationRun> {
  const response = await requestJson<DataResponse<EvaluationRun>>(
    "/api/v1/admin/ai/evaluations",
    {
      method: "POST",
      body: JSON.stringify({
        task_class: "OUTCOME_INTERPRETATION",
        model_version_id: input.modelVersionId,
        prompt_policy_version_id: input.promptPolicyVersionId,
        dataset_version_id: input.datasetVersionId,
        evaluation_policy_version: input.evaluationPolicyVersion,
      }),
    },
  );
  return response.data;
}

export async function completeEvaluation(
  evaluationId: string,
  datasetManifestDigest: string,
  report: Record<string, unknown>,
): Promise<EvaluationRun> {
  const response = await requestJson<DataResponse<EvaluationRun>>(
    `/api/v1/admin/ai/evaluations/${encodeURIComponent(evaluationId)}/complete`,
    {
      method: "POST",
      body: JSON.stringify({
        dataset_manifest_digest: datasetManifestDigest,
        report,
      }),
    },
  );
  return response.data;
}

export async function listRoutingPolicies(
  taskClass = "OUTCOME_INTERPRETATION",
): Promise<RoutingPolicy[]> {
  const params = new URLSearchParams({
    task_class: taskClass,
    limit: "100",
  });
  const response = await requestJson<DataResponse<RoutingPolicy[]>>(
    `/api/v1/admin/ai/routing-policies?${params.toString()}`,
  );
  return response.data;
}

export async function createRoutingPolicy(input: {
  version: string;
  modelAlias: string;
  evaluation: EvaluationRun;
}): Promise<{
  routing_policy_id: string;
  status: RoutingPolicyStatus;
}> {
  const response = await requestJson<
    DataResponse<{
      routing_policy_id: string;
      status: RoutingPolicyStatus;
    }>
  >("/api/v1/admin/ai/routing-policies", {
    method: "POST",
    body: JSON.stringify({
      task_class: "OUTCOME_INTERPRETATION",
      version: input.version,
      model_alias: input.modelAlias,
      model_version_id: input.evaluation.model_version_id,
      prompt_policy_version_id: input.evaluation.prompt_policy_version_id,
      evaluation_run_id: input.evaluation.id,
    }),
  });
  return response.data;
}

export async function promoteRoutingPolicy(
  routingPolicyId: string,
): Promise<{
  routing_policy_id: string;
  model_version_id: string;
  task_class: string;
  routing_version: string;
  model_status: string;
  routing_status: string;
  activated_at: string;
}> {
  const response = await requestJson<
    DataResponse<{
      routing_policy_id: string;
      model_version_id: string;
      task_class: string;
      routing_version: string;
      model_status: string;
      routing_status: string;
      activated_at: string;
    }>
  >(
    `/api/v1/admin/ai/routing-policies/${encodeURIComponent(routingPolicyId)}/promote`,
    { method: "POST" },
  );
  return response.data;
}
