import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import { ApiError } from "../api/client";
import {
  approveLearningDataset,
  completeEvaluation,
  createEvaluation,
  createOutcomeDataset,
  createReviewedDecisionDataset,
  createRoutingPolicy,
  curateLearningSignal,
  executeInternalTrainingRun,
  exportLearningDataset,
  listEvaluations,
  listInternalTrainingRuns,
  listLearningDatasets,
  listLearningSignals,
  listModelVersions,
  listPromptPolicyVersions,
  listRoutingPolicies,
  promoteRoutingPolicy,
  type DatasetExport,
  type DatasetStatus,
  type EvaluationRun,
  type EvaluationStatus,
  type LearningDataset,
  type LearningSignal,
  type LearningSignalQuality,
  type InternalTrainingRun,
  type InternalTrainingRunStatus,
  type ModelVersionCatalogItem,
  type PromptPolicyVersionCatalogItem,
  type RoutingPolicy,
  type RoutingPolicyStatus,
} from "../api/learningGovernance";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  Panel,
} from "../design-system/components";

type TrainableTask =
  | "DIAGNOSIS"
  | "PRESCRIPTION"
  | "OUTCOME_INTERPRETATION";

type AdminData = {
  signals: LearningSignal[];
  datasets: LearningDataset[];
  trainingRuns: InternalTrainingRun[];
  models: ModelVersionCatalogItem[];
  prompts: PromptPolicyVersionCatalogItem[];
  evaluations: EvaluationRun[];
  routes: RoutingPolicy[];
};

type State =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "forbidden" }
  | { kind: "error"; message: string }
  | ({ kind: "ready" } & AdminData);

const qualityLabels: Record<LearningSignalQuality, string> = {
  RAW: "خام",
  CURATED: "کیوریت‌شده",
  EXCLUDED: "حذف‌شده",
};

const datasetStatusLabels: Record<DatasetStatus, string> = {
  DRAFT: "پیش‌نویس",
  APPROVED: "تأییدشده",
  RETIRED: "بازنشسته",
};

const trainingRunStatusLabels: Record<InternalTrainingRunStatus, string> = {
  RUNNING: "در حال آموزش",
  SUCCEEDED: "موفق",
  FAILED: "ناموفق",
};

const evaluationStatusLabels: Record<EvaluationStatus, string> = {
  PENDING: "در انتظار اجرا",
  RUNNING: "در حال اجرا",
  PASSED: "گذر کرده",
  FAILED: "ناموفق",
};

const routingStatusLabels: Record<RoutingPolicyStatus, string> = {
  DRAFT: "پیش‌نویس",
  ACTIVE: "فعال تولید",
  RETIRED: "بازنشسته",
};

const signalTypeLabels: Record<string, string> = {
  DIAGNOSIS_CONFIRMED: "تأیید تشخیص",
  DIAGNOSIS_MODIFIED: "اصلاح تشخیص",
  DIAGNOSIS_REPLACED: "جایگزینی تشخیص",
  DIAGNOSIS_REJECTED: "رد تشخیص",
  DIAGNOSIS_DEFERRED: "تعویق تشخیص",
  PRESCRIPTION_CONFIRMED: "تأیید نسخه",
  PRESCRIPTION_MODIFIED: "اصلاح نسخه",
  PRESCRIPTION_REPLACED: "جایگزینی نسخه",
  PRESCRIPTION_DEFERRED: "تعویق نسخه",
  PROVIDER_SELECTED: "انتخاب ارائه‌دهنده",
  OUTCOME_OBSERVED: "Outcome مشاهده‌شده",
};

const persianDateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function qualityTone(
  status: LearningSignalQuality,
): "neutral" | "success" | "danger" {
  if (status === "CURATED") return "success";
  if (status === "EXCLUDED") return "danger";
  return "neutral";
}

function datasetTone(
  status: DatasetStatus,
): "neutral" | "success" | "warning" {
  if (status === "APPROVED") return "success";
  if (status === "DRAFT") return "warning";
  return "neutral";
}

function trainingRunTone(
  status: InternalTrainingRunStatus,
): "accent" | "success" | "danger" {
  if (status === "SUCCEEDED") return "success";
  if (status === "FAILED") return "danger";
  return "accent";
}

function evaluationTone(
  status: EvaluationStatus,
): "neutral" | "accent" | "success" | "danger" {
  if (status === "PASSED") return "success";
  if (status === "FAILED") return "danger";
  if (status === "PENDING" || status === "RUNNING") return "accent";
  return "neutral";
}

function routingTone(
  status: RoutingPolicyStatus,
): "neutral" | "accent" | "success" {
  if (status === "ACTIVE") return "success";
  if (status === "DRAFT") return "accent";
  return "neutral";
}

function parseJsonObject(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value) as unknown;
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      !Array.isArray(parsed)
    ) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return null;
  }
  return null;
}

function shortId(value: string | null): string {
  if (!value) return "—";
  return value.length <= 12 ? value : `${value.slice(0, 8)}…${value.slice(-4)}`;
}

export function LearningGovernancePage() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [signalQualityFilter, setSignalQualityFilter] = useState<
    LearningSignalQuality | "ALL"
  >("RAW");
  const [signalTypeFilter, setSignalTypeFilter] = useState<string>("ALL");
  const [curationSignalId, setCurationSignalId] = useState<string | null>(null);
  const [curationTarget, setCurationTarget] = useState<
    "CURATED" | "EXCLUDED"
  >("CURATED");
  const [curationReason, setCurationReason] = useState(
    "OUTCOME_REVIEW_PROVENANCE_VERIFIED",
  );
  const [selectedSignalIds, setSelectedSignalIds] = useState<Set<string>>(
    new Set(),
  );

  const [datasetTaskClass, setDatasetTaskClass] =
    useState<TrainableTask>("OUTCOME_INTERPRETATION");
  const [datasetKey, setDatasetKey] = useState("outcome-interpretation");
  const [datasetVersion, setDatasetVersion] = useState("");
  const [selectionPolicyVersion, setSelectionPolicyVersion] = useState(
    "outcome-learning-selection-v1",
  );
  const [exportPreview, setExportPreview] = useState<DatasetExport | null>(null);

  const [trainingDatasetId, setTrainingDatasetId] = useState("");
  const [trainingModelKey, setTrainingModelKey] = useState(
    "hamoon.gemma4.12b",
  );
  const [trainingVersion, setTrainingVersion] = useState("");
  const [trainingModelId, setTrainingModelId] = useState(
    "google/gemma-4-12B-it@707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
  );
  const [trainingPipelineVersion, setTrainingPipelineVersion] = useState(
    "gemma4-12b-it-sft-lora-v1",
  );
  const [trainingBaseModelVersionId, setTrainingBaseModelVersionId] =
    useState("");
  const [trainingLimitations, setTrainingLimitations] = useState("");

  const [evaluationDatasetId, setEvaluationDatasetId] = useState("");
  const [evaluationModelId, setEvaluationModelId] = useState("");
  const [evaluationPromptId, setEvaluationPromptId] = useState("");
  const [evaluationPolicyVersion, setEvaluationPolicyVersion] =
    useState("outcome-evaluation-v1");

  const [attestationEvaluationId, setAttestationEvaluationId] = useState("");
  const [evaluationReportJson, setEvaluationReportJson] = useState("");

  const [routingEvaluationId, setRoutingEvaluationId] = useState("");
  const [routingVersion, setRoutingVersion] = useState("");
  const [routingModelAlias, setRoutingModelAlias] = useState("");

  const [promotionRouteId, setPromotionRouteId] = useState<string | null>(null);
  const [promotionAcknowledged, setPromotionAcknowledged] = useState(false);

  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setActionError(null);
    try {
      const [
        signals,
        datasets,
        trainingRuns,
        models,
        prompts,
        evaluations,
        routes,
      ] = await Promise.all([
          listLearningSignals(),
          listLearningDatasets(),
          listInternalTrainingRuns(),
          listModelVersions(),
          listPromptPolicyVersions(),
          listEvaluations(),
          listRoutingPolicies(),
        ]);
      setState({
        kind: "ready",
        signals,
        datasets,
        trainingRuns,
        models,
        prompts,
        evaluations,
        routes,
      });
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
        setState({ kind: "auth-required" });
      } else if (error instanceof ApiError && error.status === 403) {
        setState({ kind: "forbidden" });
      } else {
        setState({
          kind: "error",
          message: "اطلاعات کنسول یادگیری و حاکمیت دریافت نشد.",
        });
      }
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const ready = state.kind === "ready" ? state : null;

  const filteredSignals = useMemo(() => {
    if (!ready) return [];
    return ready.signals.filter(
      (signal) =>
        (signalQualityFilter === "ALL" ||
          signal.quality_status === signalQualityFilter) &&
        (signalTypeFilter === "ALL" ||
          signal.signal_type === signalTypeFilter),
    );
  }, [ready, signalQualityFilter, signalTypeFilter]);

  const eligibleDatasetSignals = useMemo(() => {
    if (!ready) return [];
    return ready.signals.filter((signal) => {
      if (signal.quality_status !== "CURATED") return false;
      if (datasetTaskClass === "OUTCOME_INTERPRETATION") {
        return (
          signal.signal_type === "OUTCOME_OBSERVED" &&
          signal.outcome_id !== null &&
          signal.provider_result_id !== null &&
          signal.intervention_id !== null
        );
      }
      if (datasetTaskClass === "DIAGNOSIS") {
        return (
          signal.ai_decision_id !== null &&
          signal.diagnosis_id !== null &&
          [
            "DIAGNOSIS_CONFIRMED",
            "DIAGNOSIS_MODIFIED",
            "DIAGNOSIS_REPLACED",
          ].includes(signal.signal_type)
        );
      }
      return (
        signal.ai_decision_id !== null &&
        signal.prescription_id !== null &&
        [
          "PRESCRIPTION_CONFIRMED",
          "PRESCRIPTION_MODIFIED",
          "PRESCRIPTION_REPLACED",
        ].includes(signal.signal_type)
      );
    });
  }, [datasetTaskClass, ready]);

  const approvedDatasets = useMemo(
    () => ready?.datasets.filter((item) => item.status === "APPROVED") ?? [],
    [ready],
  );

  const trainableDatasets = useMemo(
    () =>
      approvedDatasets.filter((item) =>
        ["DIAGNOSIS", "PRESCRIPTION", "OUTCOME_INTERPRETATION"].includes(
          item.purpose,
        ),
      ),
    [approvedDatasets],
  );

  const growthBaseModels = useMemo(() => {
    const dataset = ready?.datasets.find(
      (item) => item.id === trainingDatasetId,
    );
    if (!ready || !dataset) return [];
    return ready.models.filter(
      (item) =>
        item.provider_code === "INTERNAL_MODEL" &&
        item.provider_status === "ACTIVE" &&
        item.artifact_sha256 !== null &&
        (item.status === "APPROVED" || item.status === "PRODUCTION") &&
        item.purpose === dataset.purpose,
    );
  }, [ready, trainingDatasetId]);

  const eligibleModels = useMemo(
    () =>
      ready?.models.filter(
        (item) =>
          item.provider_status === "ACTIVE" &&
          item.provider_code === "INTERNAL_MODEL" &&
          item.artifact_sha256 !== null &&
          (item.status === "CANDIDATE" || item.status === "APPROVED") &&
          item.purpose === "OUTCOME_INTERPRETATION",
      ) ?? [],
    [ready],
  );

  const activePrompts = useMemo(
    () =>
      ready?.prompts.filter(
        (item) =>
          item.status === "ACTIVE" &&
          (item.purpose === "OUTCOME_INTERPRETATION" ||
            item.output_schema_version === "outcome-interpretation-v1"),
      ) ?? [],
    [ready],
  );

  const pendingEvaluations = useMemo(
    () =>
      ready?.evaluations.filter(
        (item) => item.status === "PENDING" || item.status === "RUNNING",
      ) ?? [],
    [ready],
  );

  const passedEvaluations = useMemo(
    () =>
      ready?.evaluations.filter(
        (item) =>
          item.status === "PASSED" &&
          item.passed &&
          item.dataset_manifest_digest !== null &&
          item.report_digest !== null &&
          item.summary_metrics.structural_gate_passed === true,
      ) ?? [],
    [ready],
  );

  const draftRoutes = useMemo(
    () => ready?.routes.filter((item) => item.status === "DRAFT") ?? [],
    [ready],
  );

  const signalById = useMemo(
    () => new Map(ready?.signals.map((item) => [item.id, item]) ?? []),
    [ready],
  );
  const datasetById = useMemo(
    () => new Map(ready?.datasets.map((item) => [item.id, item]) ?? []),
    [ready],
  );
  const modelById = useMemo(
    () => new Map(ready?.models.map((item) => [item.id, item]) ?? []),
    [ready],
  );
  const promptById = useMemo(
    () => new Map(ready?.prompts.map((item) => [item.id, item]) ?? []),
    [ready],
  );
  const evaluationById = useMemo(
    () => new Map(ready?.evaluations.map((item) => [item.id, item]) ?? []),
    [ready],
  );

  async function runAction(
    key: string,
    action: () => Promise<void>,
    successMessage: string,
  ) {
    setBusy(key);
    setActionError(null);
    setActionMessage(null);
    try {
      await action();
      setActionMessage(successMessage);
      await load();
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        setActionError(
          "نسخه یا وضعیت منبع هم‌زمان تغییر کرده است. اطلاعات تازه بارگذاری شد؛ اقدام را دوباره بررسی کنید.",
        );
        await load();
      } else if (error instanceof ApiError && error.status === 422) {
        setActionError(
          `Gate حاکمیتی این اقدام را نپذیرفت: ${error.code}`,
        );
      } else if (error instanceof ApiError && error.status === 403) {
        setActionError("این عملیات فقط برای نقش ADMIN مجاز است.");
      } else {
        setActionError("انجام عملیات موفق نبود.");
      }
    } finally {
      setBusy(null);
    }
  }

  async function submitCuration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!curationSignalId || !curationReason.trim()) return;
    const signal = signalById.get(curationSignalId);
    if (!signal) return;

    await runAction(
      `curate:${signal.id}`,
      async () => {
        await curateLearningSignal(
          signal,
          curationTarget,
          curationReason.trim(),
        );
        setCurationSignalId(null);
        if (curationTarget === "CURATED") {
          setSelectedSignalIds((current) => {
            const next = new Set(current);
            next.add(signal.id);
            return next;
          });
        }
      },
      curationTarget === "CURATED"
        ? "Learning Signal کیوریت شد."
        : "Learning Signal از ورودی یادگیری خارج شد.",
    );
  }

  function toggleDatasetSignal(signalId: string) {
    setSelectedSignalIds((current) => {
      const next = new Set(current);
      if (next.has(signalId)) next.delete(signalId);
      else next.add(signalId);
      return next;
    });
  }

  async function submitDataset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const signalIds = [...selectedSignalIds].filter((id) =>
      eligibleDatasetSignals.some((signal) => signal.id === id),
    );
    if (
      !datasetKey.trim() ||
      !datasetVersion.trim() ||
      !selectionPolicyVersion.trim() ||
      signalIds.length === 0
    ) {
      setActionError(
        "کلید، نسخه، policy انتخاب و حداقل یک Learning Signal کیوریت‌شده الزامی است.",
      );
      return;
    }
    await runAction(
      "create-dataset",
      async () => {
        if (datasetTaskClass === "OUTCOME_INTERPRETATION") {
          await createOutcomeDataset({
            datasetKey: datasetKey.trim(),
            version: datasetVersion.trim(),
            selectionPolicyVersion: selectionPolicyVersion.trim(),
            signalIds,
          });
        } else {
          await createReviewedDecisionDataset({
            taskClass: datasetTaskClass,
            datasetKey: datasetKey.trim(),
            version: datasetVersion.trim(),
            selectionPolicyVersion: selectionPolicyVersion.trim(),
            signalIds,
          });
        }
        setSelectedSignalIds(new Set());
      },
      "Dataset نسخه‌دار ساخته شد و manifest آن قفل شد.",
    );
  }

  async function submitInternalTrainingRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const dataset = ready?.datasets.find(
      (item) => item.id === trainingDatasetId,
    );
    if (
      !dataset ||
      dataset.status !== "APPROVED" ||
      !["DIAGNOSIS", "PRESCRIPTION", "OUTCOME_INTERPRETATION"].includes(
        dataset.purpose,
      ) ||
      !trainingModelKey.trim() ||
      !trainingVersion.trim() ||
      !trainingModelId.trim() ||
      !trainingPipelineVersion.trim()
    ) {
      setActionError(
        "Dataset تأییدشده، مشخصات مدل و نسخه pipeline داخلی الزامی است.",
      );
      return;
    }
    await runAction(
      "execute-internal-training",
      async () => {
        await executeInternalTrainingRun({
          taskClass: dataset.purpose as TrainableTask,
          datasetVersionId: dataset.id,
          modelKey: trainingModelKey.trim(),
          version: trainingVersion.trim(),
          modelId: trainingModelId.trim(),
          trainingPipelineVersion: trainingPipelineVersion.trim(),
          baseModelVersionId: trainingBaseModelVersionId || undefined,
          limitations: trainingLimitations.trim(),
        });
        setTrainingVersion("");
        setTrainingPipelineVersion("");
        setTrainingBaseModelVersionId("");
        setTrainingLimitations("");
      },
      "Training Run داخلی اجرا شد؛ در صورت موفقیت artifact immutable و CANDIDATE ساخته شد.",
    );
  }

  async function approveDataset(dataset: LearningDataset) {
    await runAction(
      `approve-dataset:${dataset.id}`,
      async () => {
        await approveLearningDataset(dataset.id);
      },
      "Dataset برای Evaluation تأیید شد.",
    );
  }

  async function previewDataset(dataset: LearningDataset) {
    setBusy(`export:${dataset.id}`);
    setActionError(null);
    try {
      setExportPreview(await exportLearningDataset(dataset.id));
    } catch {
      setActionError("Export دیتاست دریافت نشد.");
    } finally {
      setBusy(null);
    }
  }

  async function submitEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !evaluationDatasetId ||
      !evaluationModelId ||
      !evaluationPromptId ||
      !evaluationPolicyVersion.trim()
    ) {
      setActionError("Dataset، مدل، Prompt و نسخه Evaluation Policy الزامی‌اند.");
      return;
    }
    await runAction(
      "create-evaluation",
      async () => {
        const created = await createEvaluation({
          datasetVersionId: evaluationDatasetId,
          modelVersionId: evaluationModelId,
          promptPolicyVersionId: evaluationPromptId,
          evaluationPolicyVersion: evaluationPolicyVersion.trim(),
        });
        setAttestationEvaluationId(created.id);
        setEvaluationReportJson("");
      },
      "Evaluation Run ایجاد شد. نتیجه Offline Evaluator باید جداگانه attest شود.",
    );
  }

  async function submitAttestation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const evaluation = evaluationById.get(attestationEvaluationId);
    if (!evaluation || !evaluation.dataset_manifest_digest) {
      setActionError("Evaluation معتبر با manifest digest لازم است.");
      return;
    }
    const report = parseJsonObject(evaluationReportJson);
    if (!report) {
      setActionError("گزارش Evaluation باید یک JSON object معتبر باشد.");
      return;
    }
    if (report.policy_version !== evaluation.evaluation_policy_version) {
      setActionError(
        "policy_version گزارش با Evaluation Policy ثبت‌شده یکسان نیست.",
      );
      return;
    }
    await runAction(
      `complete-evaluation:${evaluation.id}`,
      async () => {
        await completeEvaluation(
          evaluation.id,
          evaluation.dataset_manifest_digest as string,
          report,
        );
        setEvaluationReportJson("");
      },
      "گزارش attest شد و gate ساختاری Evaluation ثبت شد.",
    );
  }

  async function submitRoutingDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const evaluation = evaluationById.get(routingEvaluationId);
    if (!evaluation || !routingVersion.trim() || !routingModelAlias.trim()) {
      setActionError("Evaluation گذرکرده، نسخه route و model alias الزامی‌اند.");
      return;
    }
    await runAction(
      "create-routing",
      async () => {
        const created = await createRoutingPolicy({
          version: routingVersion.trim(),
          modelAlias: routingModelAlias.trim(),
          evaluation,
        });
        setPromotionRouteId(created.routing_policy_id);
        setPromotionAcknowledged(false);
      },
      "Routing Policy فقط در وضعیت DRAFT ساخته شد؛ هنوز Production تغییر نکرده است.",
    );
  }

  async function promoteRoute() {
    if (!promotionRouteId || !promotionAcknowledged) return;
    const route = ready?.routes.find((item) => item.id === promotionRouteId);
    if (!route || route.status !== "DRAFT") return;

    await runAction(
      `promote:${route.id}`,
      async () => {
        await promoteRoutingPolicy(route.id);
        setPromotionRouteId(null);
        setPromotionAcknowledged(false);
      },
      "Routing Policy با تأیید صریح انسانی به Production ترویج شد.",
    );
  }

  if (state.kind === "loading") {
    return <LoadingState label="در حال بارگذاری کنسول یادگیری و حاکمیت…" />;
  }

  if (state.kind === "auth-required") {
    return (
      <EmptyState
        title="ورود سازمانی لازم است"
        description="برای کنسول حاکمیت AI باید توکن سازمانی معتبر داشته باشید."
      />
    );
  }

  if (state.kind === "forbidden") {
    return (
      <ErrorState
        title="دسترسی مدیریتی لازم است"
        description="مشاهده یا تغییر Learning Governance فقط برای ADMIN یا در بخش‌های خواندنی برای SECURITY_AUDITOR مجاز است."
      />
    );
  }

  if (state.kind === "error") {
    return (
      <ErrorState
        description={state.message}
        action={
          <Button variant="secondary" onClick={() => void load()}>
            تلاش دوباره
          </Button>
        }
      />
    );
  }

  const readyData = state;
  const rawCount = readyData.signals.filter(
    (item) => item.quality_status === "RAW",
  ).length;
  const curatedOutcomeCount = eligibleDatasetSignals.length;
  const approvedDatasetCount = approvedDatasets.length;
  const passedEvaluationCount = passedEvaluations.length;
  const activeRoute = readyData.routes.find((item) => item.status === "ACTIVE");

  return (
    <div className="page-stack admin-learning-page">
      <header className="admin-learning-hero">
        <div>
          <span className="eyebrow">کنسول مدیریتی هامون</span>
          <h1>یادگیری و حاکمیت AI</h1>
          <p>
            مسیر Production فقط از Signal کیوریت‌شده، Dataset نسخه‌دار، Evaluation
            attest‌شده و Promotion صریح انسانی عبور می‌کند.
          </p>
        </div>
        <Badge tone={activeRoute ? "success" : "warning"}>
          {activeRoute
            ? `Route فعال: ${activeRoute.version}`
            : "Route فعال Outcome یافت نشد"}
        </Badge>
      </header>

      {actionError ? (
        <div className="inline-alert" role="alert">{actionError}</div>
      ) : null}
      {actionMessage ? (
        <div className="admin-success-message" role="status">
          {actionMessage}
        </div>
      ) : null}

      <section className="admin-metric-grid">
        <MetricCard label="Signal خام" value={rawCount.toLocaleString("fa-IR")} />
        <MetricCard
          label="Outcome کیوریت‌شده"
          value={curatedOutcomeCount.toLocaleString("fa-IR")}
        />
        <MetricCard
          label="Dataset تأییدشده"
          value={approvedDatasetCount.toLocaleString("fa-IR")}
        />
        <MetricCard
          label="Evaluation گذرکرده"
          value={passedEvaluationCount.toLocaleString("fa-IR")}
        />
      </section>

      <div className="governance-flow">
        <span>Learning Signal</span>
        <b>→</b>
        <span>Curation</span>
        <b>→</b>
        <span>Dataset DRAFT</span>
        <b>→</b>
        <span>Dataset APPROVED</span>
        <b>→</b>
        <span>Offline Evaluation</span>
        <b>→</b>
        <span>Routing DRAFT</span>
        <b>→</b>
        <span>Human Promotion</span>
      </div>

      <Panel className="admin-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">ورودی خام حلقه یادگیری</span>
            <h2>Learning Signal Queue</h2>
          </div>
          <Badge tone="neutral">
            {filteredSignals.length.toLocaleString("fa-IR")} مورد
          </Badge>
        </div>

        <div className="admin-filter-bar">
          <label>
            <span>کیفیت</span>
            <select
              onChange={(event) =>
                setSignalQualityFilter(
                  event.target.value as LearningSignalQuality | "ALL",
                )
              }
              value={signalQualityFilter}
            >
              <option value="ALL">همه</option>
              <option value="RAW">خام</option>
              <option value="CURATED">کیوریت‌شده</option>
              <option value="EXCLUDED">حذف‌شده</option>
            </select>
          </label>
          <label>
            <span>نوع Signal</span>
            <select
              onChange={(event) => setSignalTypeFilter(event.target.value)}
              value={signalTypeFilter}
            >
              <option value="ALL">همه انواع</option>
              {Object.entries(signalTypeLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="learning-signal-list">
          {filteredSignals.length === 0 ? (
            <EmptyState
              title="Signal مطابق فیلتر وجود ندارد"
              description="فیلترها را تغییر دهید یا پس از ثبت تصمیم‌های انسانی دوباره این صف را بررسی کنید."
            />
          ) : (
            filteredSignals.map((signal) => {
              const datasetEligible =
                signal.quality_status === "CURATED" &&
                signal.signal_type === "OUTCOME_OBSERVED" &&
                signal.outcome_id !== null &&
                signal.provider_result_id !== null &&
                signal.intervention_id !== null;
              return (
                <article className="learning-signal-row" key={signal.id}>
                  <div className="learning-signal-row__check">
                    <input
                      aria-label="انتخاب برای دیتاست"
                      checked={selectedSignalIds.has(signal.id)}
                      disabled={!datasetEligible}
                      onChange={() => toggleDatasetSignal(signal.id)}
                      type="checkbox"
                    />
                  </div>
                  <div className="learning-signal-row__main">
                    <div>
                      <strong>
                        {signalTypeLabels[signal.signal_type] ??
                          signal.signal_type}
                      </strong>
                      <span>{signal.signal_label}</span>
                    </div>
                    <div className="learning-signal-row__meta">
                      <Badge tone={qualityTone(signal.quality_status)}>
                        {qualityLabels[signal.quality_status]}
                      </Badge>
                      <span>
                        {persianDateTime.format(new Date(signal.created_at))}
                      </span>
                      <span className="ltr-value">
                        Human: {shortId(signal.human_decision_id)}
                      </span>
                      {signal.outcome_id ? (
                        <span className="ltr-value">
                          Outcome: {shortId(signal.outcome_id)}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div className="learning-signal-row__actions">
                    {signal.quality_status === "RAW" ? (
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setCurationSignalId(signal.id);
                          setCurationTarget("CURATED");
                          setCurationReason(
                            signal.signal_type === "OUTCOME_OBSERVED"
                              ? "OUTCOME_REVIEW_PROVENANCE_VERIFIED"
                              : "HUMAN_DECISION_PROVENANCE_VERIFIED",
                          );
                        }}
                      >
                        بررسی کیفیت
                      </Button>
                    ) : null}
                  </div>
                </article>
              );
            })
          )}
        </div>

        {curationSignalId ? (
          <form className="curation-form" onSubmit={submitCuration}>
            <div>
              <span className="eyebrow">تصمیم کیوریشن انسانی</span>
              <strong>
                {signalTypeLabels[signalById.get(curationSignalId)?.signal_type ?? ""] ??
                  "Learning Signal"}
              </strong>
            </div>
            <label>
              <span>تصمیم</span>
              <select
                onChange={(event) =>
                  setCurationTarget(
                    event.target.value as "CURATED" | "EXCLUDED",
                  )
                }
                value={curationTarget}
              >
                <option value="CURATED">CURATED — ورود به مخزن یادگیری</option>
                <option value="EXCLUDED">EXCLUDED — عدم استفاده</option>
              </select>
            </label>
            <label>
              <span>Reason code</span>
              <input
                maxLength={100}
                onChange={(event) => setCurationReason(event.target.value)}
                value={curationReason}
              />
            </label>
            <div className="curation-form__actions">
              <Button disabled={busy === `curate:${curationSignalId}`} type="submit">
                ثبت تصمیم
              </Button>
              <Button
                type="button"
                variant="quiet"
                onClick={() => setCurationSignalId(null)}
              >
                انصراف
              </Button>
            </div>
          </form>
        ) : null}
      </Panel>

      <Panel className="admin-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Curated Human-reviewed Data</span>
            <h2>Dataset Builder</h2>
          </div>
          <Badge tone="accent">
            {selectedSignalIds.size.toLocaleString("fa-IR")} Signal انتخاب‌شده
          </Badge>
        </div>

        <form className="dataset-builder" onSubmit={submitDataset}>
          <div className="admin-form-grid">
            <label>
              <span>نوع یادگیری</span>
              <select
                value={datasetTaskClass}
                onChange={(event) => {
                  const value = event.target.value as TrainableTask;
                  setDatasetTaskClass(value);
                  setSelectedSignalIds(new Set());
                  if (value === "DIAGNOSIS") {
                    setDatasetKey("diagnosis-learning");
                    setSelectionPolicyVersion("diagnosis-reviewed-selection-v1");
                  } else if (value === "PRESCRIPTION") {
                    setDatasetKey("prescription-learning");
                    setSelectionPolicyVersion(
                      "prescription-reviewed-selection-v1",
                    );
                  } else {
                    setDatasetKey("outcome-interpretation");
                    setSelectionPolicyVersion(
                      "outcome-learning-selection-v1",
                    );
                  }
                }}
              >
                <option value="DIAGNOSIS">Diagnosis</option>
                <option value="PRESCRIPTION">Prescription</option>
                <option value="OUTCOME_INTERPRETATION">
                  Outcome Interpretation
                </option>
              </select>
            </label>
            <label>
              <span>Dataset key</span>
              <input
                maxLength={150}
                onChange={(event) => setDatasetKey(event.target.value)}
                value={datasetKey}
              />
            </label>
            <label>
              <span>Version</span>
              <input
                maxLength={100}
                onChange={(event) => setDatasetVersion(event.target.value)}
                placeholder="مثلاً 2026-10-04-r1"
                value={datasetVersion}
              />
            </label>
            <label>
              <span>Selection policy</span>
              <input
                maxLength={100}
                onChange={(event) =>
                  setSelectionPolicyVersion(event.target.value)
                }
                value={selectionPolicyVersion}
              />
            </label>
          </div>
          <div className="dataset-invariants">
            <Badge tone="success">{datasetTaskClass}</Badge>
            <span>فقط CURATED Signal با Human Review معتبر</span>
            <span>Reject/Defer وارد مدل Diagnosis/Prescription نمی‌شود</span>
            {datasetTaskClass === "OUTCOME_INTERPRETATION" ? (
              <span>Provider Result فقط structured و causal_claim=false</span>
            ) : (
              <span>Target همان payload نهایی پذیرفته‌شده توسط انسان است</span>
            )}
          </div>
          <Button disabled={busy === "create-dataset"} type="submit">
            ساخت Dataset DRAFT
          </Button>
        </form>

        <div className="dataset-list">
          {readyData.datasets.map((dataset) => (
            <article className="dataset-card" key={dataset.id}>
              <div>
                <strong>
                  {dataset.dataset_key} / {dataset.version}
                </strong>
                <span>
                  {dataset.item_count.toLocaleString("fa-IR")} case • policy{" "}
                  {dataset.selection_policy_version}
                </span>
                <span className="digest-value">
                  {dataset.manifest_digest}
                </span>
              </div>
              <div className="dataset-card__actions">
                <Badge tone={datasetTone(dataset.status)}>
                  {datasetStatusLabels[dataset.status]}
                </Badge>
                <Button
                  disabled={busy === `export:${dataset.id}`}
                  variant="quiet"
                  onClick={() => void previewDataset(dataset)}
                >
                  Export / Manifest
                </Button>
                {dataset.status === "DRAFT" ? (
                  <Button
                    disabled={busy === `approve-dataset:${dataset.id}`}
                    onClick={() => void approveDataset(dataset)}
                  >
                    تأیید Dataset
                  </Button>
                ) : null}
              </div>
            </article>
          ))}
        </div>

        {exportPreview ? (
          <div className="dataset-export-preview">
            <div>
              <strong>Export قابل ارزیابی</strong>
              <Button variant="quiet" onClick={() => setExportPreview(null)}>
                بستن
              </Button>
            </div>
            <span>
              نسخه {exportPreview.dataset_version} •{" "}
              {exportPreview.cases.length.toLocaleString("fa-IR")} case
            </span>
            <code>{exportPreview.manifest_digest}</code>
          </div>
        ) : null}
      </Panel>

      <Panel className="admin-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">APPROVED Dataset → Internal Training → Candidate</span>
            <h2>Training Engine داخلی هامون</h2>
          </div>
          <Badge tone="success">IN_PROCESS / بدون AI API</Badge>
        </div>
        <p>
          Training فقط با trainer ثبت‌شده داخل خود Hamoon اجرا می‌شود. artifact
          با SHA-256 در storage خصوصی و immutable ذخیره می‌شود و فقط خروجی
          Training Run موفق می‌تواند CANDIDATE بسازد.
        </p>
        <form className="evaluation-builder" onSubmit={submitInternalTrainingRun}>
          <div className="admin-form-grid admin-form-grid--four">
            <label>
              <span>Dataset APPROVED</span>
              <select
                value={trainingDatasetId}
                onChange={(event) => {
                  setTrainingDatasetId(event.target.value);
                  setTrainingBaseModelVersionId("");
                }}
              >
                <option value="">انتخاب کنید</option>
                {trainableDatasets.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.purpose} — {item.dataset_key} / {item.version}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Model key</span>
              <input
                disabled={Boolean(trainingBaseModelVersionId)}
                maxLength={150}
                placeholder="hamoon.outcome.native"
                value={trainingModelKey}
                onChange={(event) => setTrainingModelKey(event.target.value)}
              />
            </label>
            <label>
              <span>Model version</span>
              <input
                maxLength={100}
                placeholder="native-2026-10-r1"
                value={trainingVersion}
                onChange={(event) => setTrainingVersion(event.target.value)}
              />
            </label>
            <label>
              <span>Model ID</span>
              <input
                disabled
                maxLength={250}
                value={trainingModelId}
                onChange={(event) => setTrainingModelId(event.target.value)}
              />
            </label>
            <label>
              <span>Training pipeline version</span>
              <input
                disabled
                maxLength={150}
                value={trainingPipelineVersion}
                onChange={(event) => setTrainingPipelineVersion(event.target.value)}
              />
            </label>
            <label>
              <span>نسخه والد lineage</span>
              <select
                value={trainingBaseModelVersionId}
                onChange={(event) => {
                  const parentId = event.target.value;
                  setTrainingBaseModelVersionId(parentId);
                  const parent = growthBaseModels.find(
                    (item) => item.id === parentId,
                  );
                  if (parent) {
                    setTrainingModelKey(parent.model_key);
                    setTrainingModelId(parent.concrete_model_id);
                  }
                }}
              >
                <option value="">شروع مدل جدید</option>
                {growthBaseModels.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.model_key} / {item.version} — {item.status}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="admin-field-wide">
            <span>محدودیت‌های نسخه</span>
            <input
              maxLength={2000}
              value={trainingLimitations}
              onChange={(event) => setTrainingLimitations(event.target.value)}
            />
          </label>
          <div className="dataset-invariants">
            <span>
              Training Run هیچ Promotion خودکاری انجام نمی‌دهد؛ CANDIDATE بعد
              از ساخت artifact همچنان باید از Evaluation و Human Promotion عبور کند.
            </span>
          </div>
          <Button disabled={busy === "execute-internal-training"} type="submit">
            اجرای Training Run
          </Button>
        </form>

        <div className="dataset-list">
          {readyData.trainingRuns.map((run) => (
            <article className="dataset-card" key={run.id}>
              <div>
                <strong>
                  {run.model_key} / {run.model_version}
                </strong>
                <span>
                  {run.task_class} • pipeline {run.training_pipeline_version}
                </span>
                <span className="digest-value">
                  artifact: {run.artifact_sha256 ?? "—"}
                </span>
                {run.error_code ? (
                  <span className="ltr-value">
                    error: {run.error_code}
                  </span>
                ) : null}
              </div>
              <Badge tone={trainingRunTone(run.status)}>
                {trainingRunStatusLabels[run.status]}
              </Badge>
            </article>
          ))}
        </div>

        <div className="dataset-list">
          {readyData.models.map((model) => (
            <article className="dataset-card" key={model.id}>
              <div>
                <strong>
                  {model.model_key} / {model.version}
                </strong>
                <span>
                  {model.provider_code} • {model.purpose} • {model.status}
                </span>
                <span className="digest-value">
                  artifact: {model.artifact_sha256 ?? "بدون artifact"}
                </span>
                <span className="digest-value">
                  training dataset: {model.training_dataset_manifest_digest ?? "—"}
                </span>
                <span>
                  pipeline: {model.training_pipeline_version ?? "—"}
                </span>
                {model.parent_model_version_id ? (
                  <span className="ltr-value">
                    parent: {shortId(model.parent_model_version_id)}
                  </span>
                ) : null}
              </div>
              <Badge
                tone={
                  model.provider_code === "INTERNAL_MODEL" &&
                  model.artifact_sha256
                    ? "success"
                    : "warning"
                }
              >
                {model.provider_code === "INTERNAL_MODEL"
                  ? "مدل داخلی هامون"
                  : "غیرقابل Promotion تولیدی"}
              </Badge>
            </article>
          ))}
        </div>
      </Panel>

      <Panel className="admin-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Dataset APPROVED → Offline Gate</span>
            <h2>Evaluation Runs</h2>
          </div>
          <Badge tone="neutral">
            {readyData.evaluations.length.toLocaleString("fa-IR")} اجرا
          </Badge>
        </div>

        <form className="evaluation-builder" onSubmit={submitEvaluation}>
          <div className="admin-form-grid admin-form-grid--four">
            <label>
              <span>Dataset تأییدشده</span>
              <select
                onChange={(event) => setEvaluationDatasetId(event.target.value)}
                value={evaluationDatasetId}
              >
                <option value="">انتخاب کنید</option>
                {approvedDatasets.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.dataset_key} / {item.version}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Model Version</span>
              <select
                onChange={(event) => setEvaluationModelId(event.target.value)}
                value={evaluationModelId}
              >
                <option value="">انتخاب کنید</option>
                {eligibleModels.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.model_key} / {item.version} — {item.status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Prompt ACTIVE</span>
              <select
                onChange={(event) => setEvaluationPromptId(event.target.value)}
                value={evaluationPromptId}
              >
                <option value="">انتخاب کنید</option>
                {activePrompts.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.policy_name} / {item.version}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Evaluation policy</span>
              <input
                maxLength={100}
                onChange={(event) =>
                  setEvaluationPolicyVersion(event.target.value)
                }
                value={evaluationPolicyVersion}
              />
            </label>
          </div>
          <Button disabled={busy === "create-evaluation"} type="submit">
            شروع Evaluation Run
          </Button>
        </form>

        <div className="evaluation-list">
          {readyData.evaluations.map((evaluation) => {
            const dataset = evaluation.dataset_version_id
              ? datasetById.get(evaluation.dataset_version_id)
              : undefined;
            const model = modelById.get(evaluation.model_version_id);
            const prompt = promptById.get(evaluation.prompt_policy_version_id);
            return (
              <article className="evaluation-card" key={evaluation.id}>
                <div className="evaluation-card__top">
                  <div>
                    <strong>
                      {model
                        ? `${model.model_key} / ${model.version}`
                        : shortId(evaluation.model_version_id)}
                    </strong>
                    <span>
                      {dataset
                        ? `${dataset.dataset_key} / ${dataset.version}`
                        : "Dataset نامشخص"}{" "}
                      •{" "}
                      {prompt
                        ? `${prompt.policy_name} / ${prompt.version}`
                        : "Prompt نامشخص"}
                    </span>
                  </div>
                  <Badge tone={evaluationTone(evaluation.status)}>
                    {evaluationStatusLabels[evaluation.status]}
                  </Badge>
                </div>
                <div className="evaluation-card__meta">
                  <span>Policy: {evaluation.evaluation_policy_version}</span>
                  {evaluation.report_digest ? (
                    <span className="ltr-value">
                      report: {shortId(evaluation.report_digest)}
                    </span>
                  ) : null}
                  {evaluation.summary_metrics.structural_gate_passed !==
                  undefined ? (
                    <Badge
                      tone={
                        evaluation.summary_metrics.structural_gate_passed === true
                          ? "success"
                          : "danger"
                      }
                    >
                      structural gate{" "}
                      {evaluation.summary_metrics.structural_gate_passed === true
                        ? "PASS"
                        : "FAIL"}
                    </Badge>
                  ) : null}
                </div>
                {(evaluation.status === "PENDING" ||
                  evaluation.status === "RUNNING") ? (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setAttestationEvaluationId(evaluation.id);
                      setEvaluationReportJson("");
                    }}
                  >
                    ثبت گزارش Offline Evaluator
                  </Button>
                ) : null}
              </article>
            );
          })}
        </div>

        {attestationEvaluationId ? (
          <form className="attestation-form" onSubmit={submitAttestation}>
            <div>
              <span className="eyebrow">Report Attestation</span>
              <strong>
                Evaluation {shortId(attestationEvaluationId)}
              </strong>
            </div>
            <p>
              گزارش باید خروجی واقعی Offline Evaluator باشد. هامون digest گزارش،
              manifest دیتاست، policy_version و invariantهای causal/human-review را
              دوباره اعتبارسنجی می‌کند.
            </p>
            <textarea
              onChange={(event) => setEvaluationReportJson(event.target.value)}
              placeholder='{"dataset_version":"...","policy_version":"outcome-evaluation-v1","case_count":...,"schema_compliance":...,"classification_agreement":...,"causal_claim_violation_rate":0,"human_review_flag_rate":1,"grounding_coverage":1,"unsupported_ref_rate":0,"structural_gate_passed":true,"manual_approval_required":true,"eligible_for_manual_approval":true,"case_metrics":[...]}'
              rows={12}
              value={evaluationReportJson}
            />
            <div className="attestation-form__actions">
              <Button
                disabled={
                  busy ===
                  `complete-evaluation:${attestationEvaluationId}`
                }
                type="submit"
              >
                Attest و ثبت نتیجه
              </Button>
              <Button
                type="button"
                variant="quiet"
                onClick={() => setAttestationEvaluationId("")}
              >
                انصراف
              </Button>
            </div>
          </form>
        ) : null}
      </Panel>

      <Panel className="admin-section promotion-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Passed Gate ≠ Production</span>
            <h2>Routing Policy و Promotion</h2>
          </div>
          <Badge tone="warning">تأیید انسانی اجباری</Badge>
        </div>

        <form className="routing-builder" onSubmit={submitRoutingDraft}>
          <div className="admin-form-grid">
            <label>
              <span>Evaluation PASSED</span>
              <select
                onChange={(event) => setRoutingEvaluationId(event.target.value)}
                value={routingEvaluationId}
              >
                <option value="">انتخاب کنید</option>
                {passedEvaluations.map((evaluation) => {
                  const model = modelById.get(evaluation.model_version_id);
                  return (
                    <option key={evaluation.id} value={evaluation.id}>
                      {model
                        ? `${model.model_key} / ${model.version}`
                        : shortId(evaluation.id)}
                    </option>
                  );
                })}
              </select>
            </label>
            <label>
              <span>Routing version</span>
              <input
                maxLength={100}
                onChange={(event) => setRoutingVersion(event.target.value)}
                placeholder="مثلاً outcome-route-v4"
                value={routingVersion}
              />
            </label>
            <label>
              <span>Model alias</span>
              <input
                maxLength={150}
                onChange={(event) => setRoutingModelAlias(event.target.value)}
                placeholder="مثلاً hamoon.outcome.v2"
                value={routingModelAlias}
              />
            </label>
          </div>
          <Button disabled={busy === "create-routing"} type="submit">
            ساخت Routing Policy DRAFT
          </Button>
        </form>

        <div className="routing-list">
          {readyData.routes.map((route) => {
            const evaluation = evaluationById.get(route.evaluation_run_id);
            const model = modelById.get(route.model_version_id);
            return (
              <article className="routing-card" key={route.id}>
                <div>
                  <strong>{route.version}</strong>
                  <span>
                    {route.model_alias} •{" "}
                    {model
                      ? `${model.model_key} / ${model.version}`
                      : shortId(route.model_version_id)}
                  </span>
                  <span>
                    Evaluation:{" "}
                    {evaluation
                      ? evaluationStatusLabels[evaluation.status]
                      : shortId(route.evaluation_run_id)}
                  </span>
                </div>
                <div className="routing-card__actions">
                  <Badge tone={routingTone(route.status)}>
                    {routingStatusLabels[route.status]}
                  </Badge>
                  {route.status === "DRAFT" ? (
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setPromotionRouteId(route.id);
                        setPromotionAcknowledged(false);
                      }}
                    >
                      بازبینی Promotion
                    </Button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>

        {promotionRouteId ? (
          <div className="promotion-confirmation">
            <div>
              <span className="eyebrow">Explicit Production Approval</span>
              <strong>
                {readyData.routes.find((item) => item.id === promotionRouteId)
                  ?.version ?? "Routing Policy"}
              </strong>
            </div>
            <p>
              این اقدام route فعال قبلی همین task را RETIRED می‌کند، Model Version
              را PRODUCTION و این Routing Policy را ACTIVE می‌کند. Evaluation پاس‌شده
              فقط شرایط لازم است و به‌تنهایی اجازه Production نمی‌دهد.
            </p>
            <label>
              <input
                checked={promotionAcknowledged}
                onChange={(event) =>
                  setPromotionAcknowledged(event.target.checked)
                }
                type="checkbox"
              />
              <span>
                تأیید می‌کنم Dataset attestation، Evaluation report و مدل/Prompt
                انتخاب‌شده را بازبینی کرده‌ام و Promotion به Production را صریحاً
                تصویب می‌کنم.
              </span>
            </label>
            <div>
              <Button
                disabled={
                  !promotionAcknowledged ||
                  busy === `promote:${promotionRouteId}`
                }
                onClick={() => void promoteRoute()}
              >
                Promote به Production
              </Button>
              <Button
                variant="quiet"
                onClick={() => {
                  setPromotionRouteId(null);
                  setPromotionAcknowledged(false);
                }}
              >
                انصراف
              </Button>
            </div>
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
