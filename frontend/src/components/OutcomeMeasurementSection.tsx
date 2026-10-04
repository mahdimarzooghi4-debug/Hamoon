import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import { ApiError } from "../api/client";
import { getWorkQueue, type WorkItem } from "../api/operations";
import {
  acceptAssessmentObservation,
  calculateOfficialPGOR,
  changeAssessmentObservationValidation,
  getAssessmentReadiness,
  getAssessmentWorkspace,
  getOutcome,
  getOutcomeInterpretation,
  getPGORSnapshot,
  getReassessmentPlan,
  listDataSources,
  listProviderResults,
  recordAssessmentObservation,
  reviewOutcome,
  startPlannedReassessment,
  type AssessmentReadiness,
  type AssessmentWorkspace,
  type AssessmentWorkspaceIndicator,
  type DataSource,
  type Outcome,
  type OutcomeClassification,
  type OutcomeInterpretation,
  type PGORSnapshot,
  type ProviderResult,
  type ReassessmentPlan,
} from "../api/measurement";
import {
  getLatestReferral,
  listHouseholdInterventions,
  type Referral,
} from "../api/providerReferral";
import type { Intervention } from "../api/prescriptions";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
} from "../design-system/components";

type MeasurementCandidate = {
  intervention: Intervention;
  referral: Referral;
  result: ProviderResult;
};

type ReadyState = {
  candidates: MeasurementCandidate[];
  selected: MeasurementCandidate | null;
  plan: ReassessmentPlan | null;
  workItem: WorkItem | null;
  workspace: AssessmentWorkspace | null;
  readiness: AssessmentReadiness | null;
  sources: DataSource[];
  preSnapshot: PGORSnapshot | null;
  postSnapshot: PGORSnapshot | null;
  outcome: Outcome | null;
  interpretation: OutcomeInterpretation | null;
};

type State =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "error"; message: string }
  | ({ kind: "ready" } & ReadyState);

type ReviewMode = "MODIFY" | "MORE_TIME" | "MORE_DATA" | null;

const planLabels: Record<string, string> = {
  SCHEDULED: "بازسنجی زمان‌بندی‌شده",
  TASK_CREATED: "آماده شروع بازسنجی",
  REASSESSMENT_STARTED: "بازسنجی در حال انجام",
  POST_PGOR_READY: "Post-PGOR آماده",
  OUTCOME_REVIEW: "آماده بازبینی Outcome",
  COMPLETED: "حلقه اندازه‌گیری تکمیل شده",
  CANCELLED: "بازسنجی لغو شده",
};

const resultStatusLabels: Record<string, string> = {
  COMPLETED: "خدمت تکمیل شده",
  SUCCESS: "موفق",
  PARTIAL: "تکمیل جزئی",
  FAILED: "ناموفق",
  CANCELLED: "لغو شده",
};

const validationLabels: Record<string, string> = {
  PENDING_VALIDATION: "منتظر اعتبارسنجی",
  VALIDATED: "اعتبارسنجی‌شده",
  DISPUTED: "دارای اختلاف",
  REJECTED: "ردشده",
  SUPERSEDED: "جایگزین‌شده",
};

const classificationLabels: Record<OutcomeClassification, string> = {
  GOAL_ACHIEVED: "هدف محقق شده",
  PROGRESS: "پیشرفت",
  NO_SIGNIFICANT_CHANGE: "تغییر معنادار مشاهده نشد",
  REGRESSION: "پسرفت",
  NEEDS_MORE_TIME: "نیازمند زمان بیشتر",
  NEEDS_MORE_DATA: "نیازمند داده بیشتر",
};

const reviewableClassifications: OutcomeClassification[] = [
  "GOAL_ACHIEVED",
  "PROGRESS",
  "NO_SIGNIFICANT_CHANGE",
  "REGRESSION",
];

const variableLabels = {
  P: "مشارکت",
  G: "ظرفیت رشد",
  O: "فرصت",
  R: "تاب‌آوری",
} as const;

const persianDateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function numeric(value: string | number | null): number {
  if (value === null) return 0;
  return typeof value === "number" ? value : Number(value);
}

function score(value: string | number | null): string {
  return numeric(value).toLocaleString("fa-IR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function signed(value: string | number): string {
  const number = numeric(value);
  const prefix = number > 0 ? "+" : "";
  return `${prefix}${number.toLocaleString("fa-IR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function planTone(
  status: ReassessmentPlan["status"],
): "accent" | "success" | "warning" | "danger" | "neutral" {
  if (status === "COMPLETED") return "success";
  if (status === "CANCELLED") return "danger";
  if (status === "SCHEDULED") return "warning";
  return "accent";
}

function outcomeTone(
  status: Outcome["status"],
): "accent" | "success" | "warning" | "neutral" {
  if (status === "CONFIRMED" || status === "MODIFIED") return "success";
  if (status === "NEEDS_MORE_DATA" || status === "NEEDS_MORE_TIME") return "warning";
  return "accent";
}

function isOutcomeClassification(value: unknown): value is OutcomeClassification {
  return (
    typeof value === "string" &&
    [
      "GOAL_ACHIEVED",
      "PROGRESS",
      "NO_SIGNIFICANT_CHANGE",
      "REGRESSION",
      "NEEDS_MORE_TIME",
      "NEEDS_MORE_DATA",
    ].includes(value)
  );
}

function machineProposal(interpretation: OutcomeInterpretation | null): {
  classification: OutcomeClassification | null;
  summary: string | null;
  causalClaim: boolean | null;
  refs: string[];
  flags: string[];
} {
  if (interpretation === null) {
    return {
      classification: null,
      summary: null,
      causalClaim: null,
      refs: [],
      flags: [],
    };
  }
  const raw = interpretation.machine_proposal;
  const classification = isOutcomeClassification(raw.classification)
    ? raw.classification
    : null;
  const summary =
    typeof raw.observed_change_summary === "string"
      ? raw.observed_change_summary
      : null;
  const causalClaim =
    typeof raw.causal_claim === "boolean" ? raw.causal_claim : null;
  const refs = Array.isArray(raw.supporting_feature_refs)
    ? raw.supporting_feature_refs.filter(
        (item): item is string => typeof item === "string",
      )
    : [];
  const flags = Array.isArray(raw.review_flags)
    ? raw.review_flags.filter(
        (item): item is string => typeof item === "string",
      )
    : [];
  return { classification, summary, causalClaim, refs, flags };
}

function latestResultCandidate(
  candidates: MeasurementCandidate[],
  selectedResultId: string,
): MeasurementCandidate | null {
  if (candidates.length === 0) return null;
  return (
    candidates.find((item) => item.result.id === selectedResultId) ??
    candidates[0]
  );
}

export function OutcomeMeasurementSection({
  householdId,
}: {
  householdId: string;
}) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [selectedResultId, setSelectedResultId] = useState("");
  const [scoreDrafts, setScoreDrafts] = useState<Record<string, string>>({});
  const [sourceDrafts, setSourceDrafts] = useState<Record<string, string>>({});
  const [detailDrafts, setDetailDrafts] = useState<Record<string, string>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [reviewMode, setReviewMode] = useState<ReviewMode>(null);
  const [reviewClassification, setReviewClassification] =
    useState<OutcomeClassification>("PROGRESS");
  const [reviewSummary, setReviewSummary] = useState("");
  const [reviewReason, setReviewReason] = useState("");

  const load = useCallback(
    async (preferredResultId = selectedResultId) => {
      setActionError(null);
      try {
        const [interventions, sources, workQueue] = await Promise.all([
          listHouseholdInterventions(householdId),
          listDataSources(),
          getWorkQueue(200),
        ]);

        const referrals = await Promise.all(
          interventions.map(async (intervention) => ({
            intervention,
            referral: await getLatestReferral(intervention.id),
          })),
        );

        const resultGroups = await Promise.all(
          referrals.map(async ({ intervention, referral }) => {
            if (referral === null) return [] as MeasurementCandidate[];
            const results = await listProviderResults(referral.id);
            return results.map((result) => ({
              intervention,
              referral,
              result,
            }));
          }),
        );

        const candidates = resultGroups
          .flat()
          .sort(
            (a, b) =>
              new Date(b.result.submitted_at).getTime() -
              new Date(a.result.submitted_at).getTime(),
          );
        const selected = latestResultCandidate(candidates, preferredResultId);
        if (selected !== null && selected.result.id !== selectedResultId) {
          setSelectedResultId(selected.result.id);
        }

        let plan: ReassessmentPlan | null = null;
        let workItem: WorkItem | null = null;
        let workspace: AssessmentWorkspace | null = null;
        let readiness: AssessmentReadiness | null = null;
        let preSnapshot: PGORSnapshot | null = null;
        let postSnapshot: PGORSnapshot | null = null;
        let outcome: Outcome | null = null;
        let interpretation: OutcomeInterpretation | null = null;

        if (selected?.result.reassessment_plan_id) {
          plan = await getReassessmentPlan(selected.result.reassessment_plan_id);
          workItem =
            plan.work_item_id === null
              ? null
              : workQueue.find((item) => item.id === plan?.work_item_id) ?? null;

          if (plan.post_assessment_id !== null) {
            [workspace, readiness] = await Promise.all([
              getAssessmentWorkspace(plan.post_assessment_id),
              getAssessmentReadiness(plan.post_assessment_id),
            ]);
          }

          if (plan.post_pgor_snapshot_id !== null) {
            postSnapshot = await getPGORSnapshot(plan.post_pgor_snapshot_id);
          }

          if (plan.outcome_id !== null) {
            outcome = await getOutcome(plan.outcome_id);
            [preSnapshot, interpretation] = await Promise.all([
              getPGORSnapshot(outcome.pre_pgor_snapshot_id),
              getOutcomeInterpretation(outcome.id),
            ]);
            if (postSnapshot === null) {
              postSnapshot = await getPGORSnapshot(outcome.post_pgor_snapshot_id);
            }
          }
        }

        setState({
          kind: "ready",
          candidates,
          selected,
          plan,
          workItem,
          workspace,
          readiness,
          sources,
          preSnapshot,
          postSnapshot,
          outcome,
          interpretation,
        });

        if (workspace !== null) {
          const nextScores: Record<string, string> = {};
          const nextSources: Record<string, string> = {};
          const nextDetails: Record<string, string> = {};
          for (const indicator of workspace.indicators) {
            nextScores[indicator.id] =
              indicator.latest_observation === null
                ? ""
                : String(indicator.latest_observation.raw_score_0_100);
            nextSources[indicator.id] =
              indicator.latest_observation?.source_id ??
              sources[0]?.id ??
              "";
            nextDetails[indicator.id] =
              indicator.latest_observation?.source_detail ?? "";
          }
          setScoreDrafts(nextScores);
          setSourceDrafts(nextSources);
          setDetailDrafts(nextDetails);
        }
      } catch (error: unknown) {
        if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
          setState({ kind: "auth-required" });
        } else {
          setState({
            kind: "error",
            message: "زنجیره نتیجه خدمت و بازسنجی دریافت نشد.",
          });
        }
      }
    },
    [householdId, selectedResultId],
  );

  useEffect(() => {
    setState({ kind: "loading" });
    void load("");
  }, [householdId]);

  const ready = state.kind === "ready" ? state : null;
  const proposal = useMemo(
    () => machineProposal(ready?.interpretation ?? null),
    [ready?.interpretation],
  );

  async function selectResult(resultId: string) {
    setSelectedResultId(resultId);
    setState({ kind: "loading" });
    await load(resultId);
  }

  async function runAction(key: string, action: () => Promise<void>) {
    setBusyKey(key);
    setActionError(null);
    try {
      await action();
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        setActionError(
          "اطلاعات هم‌زمان تغییر کرده است. وضعیت تازه بارگذاری شد؛ اقدام را دوباره بررسی کنید.",
        );
      } else if (error instanceof ApiError && error.status === 422) {
        setActionError(
          "این اقدام با وضعیت فعلی پرونده یا قواعد اندازه‌گیری سازگار نیست.",
        );
      } else {
        setActionError("انجام این اقدام موفق نبود.");
      }
    } finally {
      setBusyKey(null);
      await load();
    }
  }

  async function startReassessment() {
    if (ready?.workItem === null || ready?.workItem === undefined) return;
    await runAction("start-reassessment", async () => {
      await startPlannedReassessment(ready.workItem as WorkItem);
    });
  }

  async function recordObservation(indicator: AssessmentWorkspaceIndicator) {
    if (ready?.workspace === null || ready?.workspace === undefined) return;
    const raw = Number(scoreDrafts[indicator.id]);
    const sourceId = sourceDrafts[indicator.id] ?? "";
    if (
      !Number.isFinite(raw) ||
      raw < indicator.score_min ||
      raw > indicator.score_max
    ) {
      setActionError(
        `امتیاز «${indicator.name_fa}» باید بین ${indicator.score_min.toLocaleString("fa-IR")} و ${indicator.score_max.toLocaleString("fa-IR")} باشد.`,
      );
      return;
    }
    if (!sourceId) {
      setActionError("منبع مشاهده را انتخاب کنید.");
      return;
    }

    await runAction(`record:${indicator.id}`, async () => {
      await recordAssessmentObservation(ready.workspace!.assessment.id, {
        indicatorId: indicator.id,
        rawScore: raw,
        sourceId,
        sourceDetail: detailDrafts[indicator.id]?.trim() || null,
        effectiveAt: new Date().toISOString(),
      });
    });
  }

  async function transitionObservation(
    indicator: AssessmentWorkspaceIndicator,
    toStatus: "VALIDATED" | "DISPUTED" | "REJECTED",
  ) {
    if (
      ready?.workspace === null ||
      ready?.workspace === undefined ||
      indicator.latest_observation === null
    ) {
      return;
    }
    await runAction(
      `validation:${indicator.id}:${toStatus}`,
      async () => {
        await changeAssessmentObservationValidation(
          ready.workspace!.assessment.id,
          indicator.latest_observation!,
          toStatus,
        );
      },
    );
  }

  async function acceptObservation(indicator: AssessmentWorkspaceIndicator) {
    if (
      ready?.workspace === null ||
      ready?.workspace === undefined ||
      indicator.latest_observation === null
    ) {
      return;
    }
    await runAction(`accept:${indicator.id}`, async () => {
      await acceptAssessmentObservation(
        ready.workspace!.assessment.id,
        indicator.id,
        indicator.latest_observation!,
      );
    });
  }

  async function calculatePGOR() {
    if (ready?.workspace === null || ready?.workspace === undefined) return;
    await runAction("calculate-pgor", async () => {
      await calculateOfficialPGOR(ready.workspace!.assessment.id);
    });
  }

  async function confirmMachineOutcome() {
    if (
      ready?.outcome === null ||
      ready?.outcome === undefined ||
      proposal.classification === null ||
      proposal.summary === null
    ) {
      return;
    }
    await runAction("outcome-confirm", async () => {
      await reviewOutcome(ready.outcome!, "confirm", {
        classification: proposal.classification!,
        observedChangeSummary: proposal.summary,
      });
    });
  }

  function openModify() {
    if (ready?.outcome === null || ready?.outcome === undefined) return;
    setReviewMode("MODIFY");
    setReviewClassification(
      proposal.classification !== null &&
        reviewableClassifications.includes(proposal.classification)
        ? proposal.classification
        : "PROGRESS",
    );
    setReviewSummary(proposal.summary ?? ready.outcome.observed_change_summary);
    setReviewReason("");
  }

  function openDefer(mode: "MORE_TIME" | "MORE_DATA") {
    setReviewMode(mode);
    setReviewReason("");
  }

  async function submitOutcomeReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (ready?.outcome === null || ready?.outcome === undefined || reviewMode === null) {
      return;
    }
    if (!reviewReason.trim()) {
      setActionError("برای تغییر یا تعویق Outcome، توضیح حرفه‌ای مددکار الزامی است.");
      return;
    }

    if (reviewMode === "MODIFY") {
      if (!reviewSummary.trim()) {
        setActionError("خلاصه تغییر مشاهده‌شده الزامی است.");
        return;
      }
      await runAction("outcome-modify", async () => {
        await reviewOutcome(ready.outcome!, "modify", {
          classification: reviewClassification,
          observedChangeSummary: reviewSummary.trim(),
          reasonCode: "CASEWORKER_OUTCOME_MODIFICATION",
          reasonText: reviewReason.trim(),
        });
      });
    } else if (reviewMode === "MORE_TIME") {
      await runAction("outcome-more-time", async () => {
        await reviewOutcome(ready.outcome!, "needs-more-time", {
          reasonCode: "CASEWORKER_NEEDS_MORE_TIME",
          reasonText: reviewReason.trim(),
        });
      });
    } else {
      await runAction("outcome-more-data", async () => {
        await reviewOutcome(ready.outcome!, "needs-more-data", {
          reasonCode: "CASEWORKER_NEEDS_MORE_DATA",
          reasonText: reviewReason.trim(),
        });
      });
    }
    setReviewMode(null);
  }

  return (
    <Panel className="measurement-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Measure → Review → Learn</span>
          <h2>نتیجه خدمت، بازسنجی و Outcome</h2>
        </div>
        {ready?.plan ? (
          <Badge tone={planTone(ready.plan.status)}>
            {planLabels[ready.plan.status]}
          </Badge>
        ) : null}
      </div>

      {actionError ? (
        <div className="inline-alert" role="alert">{actionError}</div>
      ) : null}

      {state.kind === "loading" ? (
        <LoadingState label="در حال دریافت زنجیره اندازه‌گیری…" />
      ) : null}

      {state.kind === "auth-required" ? (
        <EmptyState
          title="ورود سازمانی لازم است"
          description="نتیجه خدمت و Outcome فقط برای مددکار مجاز پرونده قابل مشاهده است."
        />
      ) : null}

      {state.kind === "error" ? (
        <ErrorState
          description={state.message}
          action={
            <Button variant="secondary" onClick={() => void load()}>
              تلاش دوباره
            </Button>
          }
        />
      ) : null}

      {ready && ready.candidates.length === 0 ? (
        <EmptyState
          title="هنوز نتیجه‌ای از ارائه‌دهنده ثبت نشده است"
          description="بعد از ارسال ارجاع و دریافت نتیجه ساختاریافته ارائه‌دهنده، برنامه بازسنجی خودکار در این بخش ظاهر می‌شود."
        />
      ) : null}

      {ready && ready.selected !== null ? (
        <>
          <div className="measurement-result-picker">
            <label>
              <span>نتیجه خدمت</span>
              <select
                onChange={(event) => void selectResult(event.target.value)}
                value={ready.selected.result.id}
              >
                {ready.candidates.map((item) => (
                  <option key={item.result.id} value={item.result.id}>
                    {item.referral.provider_name} — {item.result.result_type} —{" "}
                    {persianDateTime.format(new Date(item.result.submitted_at))}
                  </option>
                ))}
              </select>
            </label>
            <Button variant="secondary" onClick={() => void load()}>
              تازه‌سازی زنجیره
            </Button>
          </div>

          <div className="provider-result-card">
            <div className="provider-result-card__top">
              <div>
                <span className="eyebrow">گزارش ارائه‌دهنده</span>
                <h3>{ready.selected.referral.provider_name}</h3>
              </div>
              <Badge tone="success">
                {resultStatusLabels[ready.selected.result.result_status] ??
                  ready.selected.result.result_status}
              </Badge>
            </div>
            <div className="provider-result-card__facts">
              <div>
                <span>نوع نتیجه</span>
                <strong>{ready.selected.result.result_type}</strong>
              </div>
              <div>
                <span>زمان ثبت</span>
                <strong>
                  {persianDateTime.format(
                    new Date(ready.selected.result.submitted_at),
                  )}
                </strong>
              </div>
              <div>
                <span>شواهد پیوست</span>
                <strong>
                  {ready.selected.result.evidence.length.toLocaleString("fa-IR")}
                </strong>
              </div>
            </div>
            <p>{ready.selected.result.result_summary}</p>
            <div className="measurement-safety-note">
              متن آزاد ارائه‌دهنده برای اثبات علت Outcome استفاده نمی‌شود؛ مسیر
              یادگیری Outcome فقط داده‌های ساختاریافته و PGOR رسمی را مصرف می‌کند.
            </div>
          </div>

          {ready.plan === null ? (
            <EmptyState
              title="برنامه بازسنجی برای این نتیجه وجود ندارد"
              description="این Provider Result هنوز به Reassessment Plan قابل اجرا متصل نشده است."
            />
          ) : (
            <div className="reassessment-plan-card">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">برنامه بازسنجی قطعی</span>
                  <h3>{planLabels[ready.plan.status]}</h3>
                </div>
                <Badge tone={planTone(ready.plan.status)}>
                  نسخه {ready.plan.version.toLocaleString("fa-IR")}
                </Badge>
              </div>
              <div className="reassessment-plan-grid">
                <div>
                  <span>موعد بازسنجی</span>
                  <strong>{persianDateTime.format(new Date(ready.plan.due_at))}</strong>
                </div>
                <div>
                  <span>فاصله بازبینی</span>
                  <strong>
                    {ready.plan.review_after_days.toLocaleString("fa-IR")} روز
                  </strong>
                </div>
                <div>
                  <span>Policy</span>
                  <strong>{ready.plan.policy_version}</strong>
                </div>
              </div>

              {ready.plan.status === "SCHEDULED" ? (
                <div className="measurement-waiting">
                  بازسنجی برای موعد تعیین‌شده زمان‌بندی شده است. Work Item در موعد
                  مقرر توسط orchestration ساخته می‌شود.
                </div>
              ) : null}

              {ready.plan.status === "TASK_CREATED" &&
              ready.workItem !== null ? (
                <Button
                  disabled={busyKey === "start-reassessment"}
                  onClick={() => void startReassessment()}
                >
                  {busyKey === "start-reassessment"
                    ? "در حال شروع…"
                    : "شروع بازسنجی"}
                </Button>
              ) : null}

              {ready.plan.status === "TASK_CREATED" &&
              ready.workItem === null ? (
                <div className="measurement-waiting">
                  Work Item ساخته شده اما در کارتابل این مددکار دیده نمی‌شود؛ وضعیت
                  assignment را بررسی کنید.
                </div>
              ) : null}
            </div>
          )}

          {ready.workspace !== null && ready.readiness !== null ? (
            <div className="reassessment-workspace">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">
                    {ready.workspace.definition_code}{" "}
                    {ready.workspace.definition_version}
                  </span>
                  <h3>فرم بازسنجی PGOR</h3>
                </div>
                <Badge
                  tone={
                    ready.readiness.status === "READY"
                      ? "success"
                      : ready.readiness.status ===
                          "REQUIREMENT_POLICY_UNRESOLVED"
                        ? "danger"
                        : "warning"
                  }
                >
                  {ready.readiness.status === "READY"
                    ? "آماده محاسبه"
                    : ready.readiness.status ===
                        "REQUIREMENT_POLICY_UNRESOLVED"
                      ? "سیاست الزامات نامشخص"
                      : "ناقص"}
                </Badge>
              </div>

              <div className="readiness-strip">
                <div>
                  <span>Indicator پذیرفته‌شده</span>
                  <strong>
                    {ready.readiness.accepted_indicator_count.toLocaleString("fa-IR")}
                    {" / "}
                    {ready.readiness.total_indicator_count.toLocaleString("fa-IR")}
                  </strong>
                </div>
                <div>
                  <span>Completeness</span>
                  <strong>
                    {ready.readiness.completeness_ratio === null
                      ? "—"
                      : `${(
                          numeric(ready.readiness.completeness_ratio) * 100
                        ).toLocaleString("fa-IR", {
                          maximumFractionDigits: 1,
                        })}٪`}
                  </strong>
                </div>
                <div>
                  <span>Validation حل‌نشده</span>
                  <strong>
                    {ready.readiness.unresolved_validation_count.toLocaleString(
                      "fa-IR",
                    )}
                  </strong>
                </div>
              </div>

              {ready.readiness.blocking_reasons.length > 0 ? (
                <div className="measurement-blockers">
                  {ready.readiness.blocking_reasons.map((reason) => (
                    <Badge key={reason} tone="warning">
                      {reason}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {ready.sources.length === 0 ? (
                <EmptyState
                  title="منبع داده فعالی وجود ندارد"
                  description="برای ثبت Observation باید حداقل یک Data Source فعال در سامانه وجود داشته باشد."
                />
              ) : (
                <div className="indicator-workspace-list">
                  {ready.workspace.indicators.map((indicator) => {
                    const observation = indicator.latest_observation;
                    return (
                      <article className="indicator-workspace-row" key={indicator.id}>
                        <div className="indicator-workspace-row__title">
                          <div>
                            <Badge tone="accent">
                              {variableLabels[indicator.variable_code]} —{" "}
                              {indicator.variable_code}
                            </Badge>
                            {indicator.required_for_complete_assessment ? (
                              <Badge tone="warning">الزامی</Badge>
                            ) : null}
                          </div>
                          <strong>{indicator.name_fa}</strong>
                          <span>{indicator.dimension_name_fa}</span>
                        </div>

                        <div className="indicator-entry-grid">
                          <label>
                            <span>امتیاز</span>
                            <input
                              max={indicator.score_max}
                              min={indicator.score_min}
                              onChange={(event) =>
                                setScoreDrafts((current) => ({
                                  ...current,
                                  [indicator.id]: event.target.value,
                                }))
                              }
                              step="0.01"
                              type="number"
                              value={scoreDrafts[indicator.id] ?? ""}
                            />
                          </label>
                          <label>
                            <span>منبع</span>
                            <select
                              onChange={(event) =>
                                setSourceDrafts((current) => ({
                                  ...current,
                                  [indicator.id]: event.target.value,
                                }))
                              }
                              value={sourceDrafts[indicator.id] ?? ""}
                            >
                              {ready.sources.map((source) => (
                                <option key={source.id} value={source.id}>
                                  {source.name}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            <span>جزئیات منبع</span>
                            <input
                              maxLength={500}
                              onChange={(event) =>
                                setDetailDrafts((current) => ({
                                  ...current,
                                  [indicator.id]: event.target.value,
                                }))
                              }
                              value={detailDrafts[indicator.id] ?? ""}
                            />
                          </label>
                          <Button
                            disabled={busyKey === `record:${indicator.id}`}
                            onClick={() => void recordObservation(indicator)}
                            variant="secondary"
                          >
                            {busyKey === `record:${indicator.id}`
                              ? "در حال ثبت…"
                              : observation === null
                                ? "ثبت مشاهده"
                                : "ثبت مشاهده جدید"}
                          </Button>
                        </div>

                        {observation !== null ? (
                          <div className="observation-state-row">
                            <div>
                              <span>آخرین Observation</span>
                              <strong>
                                {score(observation.raw_score_0_100)}
                              </strong>
                              <small>
                                {persianDateTime.format(
                                  new Date(observation.observed_at),
                                )}
                              </small>
                            </div>
                            <div>
                              <Badge
                                tone={
                                  observation.accepted
                                    ? "success"
                                    : observation.validation_status === "REJECTED"
                                      ? "danger"
                                      : "warning"
                                }
                              >
                                {observation.accepted
                                  ? "Accepted برای PGOR"
                                  : validationLabels[
                                      observation.validation_status ?? ""
                                    ] ?? "بدون وضعیت"}
                              </Badge>
                            </div>
                            <div className="observation-actions">
                              {observation.validation_status ===
                              "PENDING_VALIDATION" ? (
                                <>
                                  <Button
                                    disabled={
                                      busyKey ===
                                      `validation:${indicator.id}:VALIDATED`
                                    }
                                    onClick={() =>
                                      void transitionObservation(
                                        indicator,
                                        "VALIDATED",
                                      )
                                    }
                                  >
                                    اعتبارسنجی
                                  </Button>
                                  <Button
                                    disabled={
                                      busyKey ===
                                      `validation:${indicator.id}:REJECTED`
                                    }
                                    onClick={() =>
                                      void transitionObservation(
                                        indicator,
                                        "REJECTED",
                                      )
                                    }
                                    variant="quiet"
                                  >
                                    رد مشاهده
                                  </Button>
                                </>
                              ) : null}

                              {observation.validation_status === "VALIDATED" &&
                              !observation.accepted ? (
                                <>
                                  <Button
                                    disabled={
                                      busyKey === `accept:${indicator.id}`
                                    }
                                    onClick={() =>
                                      void acceptObservation(indicator)
                                    }
                                  >
                                    پذیرش برای PGOR
                                  </Button>
                                  <Button
                                    disabled={
                                      busyKey ===
                                      `validation:${indicator.id}:DISPUTED`
                                    }
                                    onClick={() =>
                                      void transitionObservation(
                                        indicator,
                                        "DISPUTED",
                                      )
                                    }
                                    variant="quiet"
                                  >
                                    علامت اختلاف
                                  </Button>
                                </>
                              ) : null}

                              {observation.validation_status === "DISPUTED" ? (
                                <>
                                  <Button
                                    disabled={
                                      busyKey ===
                                      `validation:${indicator.id}:VALIDATED`
                                    }
                                    onClick={() =>
                                      void transitionObservation(
                                        indicator,
                                        "VALIDATED",
                                      )
                                    }
                                  >
                                    تأیید پس از بررسی
                                  </Button>
                                  <Button
                                    disabled={
                                      busyKey ===
                                      `validation:${indicator.id}:REJECTED`
                                    }
                                    onClick={() =>
                                      void transitionObservation(
                                        indicator,
                                        "REJECTED",
                                      )
                                    }
                                    variant="quiet"
                                  >
                                    رد
                                  </Button>
                                </>
                              ) : null}
                            </div>
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              )}

              <div className="pgor-calculation-gate">
                <div>
                  <strong>محاسبه رسمی PGOR</strong>
                  <span>
                    فقط Accepted Observationها وارد موتور قطعی PGOR می‌شوند.
                  </span>
                </div>
                <Button
                  disabled={
                    ready.readiness.status !== "READY" ||
                    busyKey === "calculate-pgor"
                  }
                  onClick={() => void calculatePGOR()}
                >
                  {busyKey === "calculate-pgor"
                    ? "در حال محاسبه…"
                    : "محاسبه Post-PGOR رسمی"}
                </Button>
              </div>
            </div>
          ) : null}

          {ready.postSnapshot !== null ? (
            <div className="post-pgor-card">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">محاسبه قطعی پس از مداخله</span>
                  <h3>Post-PGOR رسمی</h3>
                </div>
                <Badge tone="success">OFFICIAL</Badge>
              </div>
              <div className="post-pgor-grid">
                {(["P", "G", "O", "R"] as const).map((code) => (
                  <div key={code}>
                    <span>{variableLabels[code]}</span>
                    <strong>
                      {code} {score(ready.postSnapshot?.[code.toLowerCase() as "p" | "g" | "o" | "r"] ?? 0)}
                    </strong>
                  </div>
                ))}
                <div className="post-pgor-grid__e">
                  <span>E</span>
                  <strong>{score(ready.postSnapshot.e)}</strong>
                </div>
              </div>
              {ready.plan?.status === "POST_PGOR_READY" ? (
                <div className="measurement-waiting">
                  Post-PGOR ثبت شده است. Temporal در حال ساخت Outcome، تفسیر AI و
                  Work Item بازبینی انسانی است.
                </div>
              ) : null}
            </div>
          ) : null}

          {ready.outcome !== null ? (
            <div className="outcome-review-card">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">تغییر مشاهده‌شده، نه ادعای علت</span>
                  <h3>Outcome</h3>
                </div>
                <Badge tone={outcomeTone(ready.outcome.status)}>
                  {ready.outcome.status === "UNDER_REVIEW"
                    ? "نیازمند تصمیم انسانی"
                    : ready.outcome.classification
                      ? classificationLabels[ready.outcome.classification]
                      : ready.outcome.status}
                </Badge>
              </div>

              <div className="outcome-delta-grid">
                {[
                  ["P", ready.outcome.p_delta],
                  ["G", ready.outcome.g_delta],
                  ["O", ready.outcome.o_delta],
                  ["R", ready.outcome.r_delta],
                  ["E", ready.outcome.e_delta],
                ].map(([code, value]) => (
                  <div key={String(code)}>
                    <span>Δ{code}</span>
                    <strong>{signed(value as string | number)}</strong>
                  </div>
                ))}
              </div>

              {ready.preSnapshot !== null && ready.postSnapshot !== null ? (
                <div className="outcome-pre-post">
                  <div>
                    <span>Pre E</span>
                    <strong>{score(ready.preSnapshot.e)}</strong>
                  </div>
                  <span>← تغییر مشاهده‌شده →</span>
                  <div>
                    <span>Post E</span>
                    <strong>{score(ready.postSnapshot.e)}</strong>
                  </div>
                </div>
              ) : null}

              {ready.interpretation === null ? (
                <div className="measurement-waiting">
                  Outcome ساخته شده اما تفسیر AI هنوز آماده نیست. بازبینی انسانی تا
                  آماده‌شدن proposal ساختاریافته باز نمی‌شود.
                </div>
              ) : (
                <div className="outcome-ai-proposal">
                  <div className="outcome-ai-proposal__meta">
                    <Badge tone="accent">پیشنهاد AI</Badge>
                    <span>{ready.interpretation.model_alias}</span>
                    <span>{ready.interpretation.output_schema_version}</span>
                    <Badge
                      tone={
                        proposal.causalClaim === false ? "success" : "danger"
                      }
                    >
                      causal_claim ={" "}
                      {proposal.causalClaim === false ? "false" : "نامعتبر"}
                    </Badge>
                  </div>
                  <strong>
                    {proposal.classification
                      ? classificationLabels[proposal.classification]
                      : "طبقه‌بندی نامعتبر"}
                  </strong>
                  <p>{proposal.summary ?? "خلاصه ساختاریافته موجود نیست."}</p>
                  {proposal.refs.length > 0 ? (
                    <div className="outcome-supporting-refs">
                      {proposal.refs.map((ref) => (
                        <span key={ref}>{ref}</span>
                      ))}
                    </div>
                  ) : null}
                  {proposal.flags.includes("HUMAN_REVIEW_REQUIRED") ? (
                    <Badge tone="warning">بازبینی انسانی الزامی</Badge>
                  ) : null}
                </div>
              )}

              {ready.outcome.status === "UNDER_REVIEW" &&
              ready.interpretation !== null ? (
                <div className="outcome-review-actions">
                  <Button
                    disabled={
                      proposal.classification === null ||
                      proposal.summary === null ||
                      proposal.causalClaim !== false ||
                      busyKey === "outcome-confirm"
                    }
                    onClick={() => void confirmMachineOutcome()}
                  >
                    تأیید پیشنهاد
                  </Button>
                  <Button variant="secondary" onClick={openModify}>
                    اصلاح تفسیر
                  </Button>
                  <Button variant="quiet" onClick={() => openDefer("MORE_TIME")}>
                    زمان بیشتر
                  </Button>
                  <Button variant="quiet" onClick={() => openDefer("MORE_DATA")}>
                    داده بیشتر
                  </Button>
                </div>
              ) : null}

              {reviewMode !== null ? (
                <form className="outcome-review-form" onSubmit={submitOutcomeReview}>
                  <div className="outcome-review-form__top">
                    <div>
                      <span className="eyebrow">تصمیم انسانی Outcome</span>
                      <h4>
                        {reviewMode === "MODIFY"
                          ? "اصلاح تفسیر"
                          : reviewMode === "MORE_TIME"
                            ? "نیازمند زمان بیشتر"
                            : "نیازمند داده بیشتر"}
                      </h4>
                    </div>
                    <button
                      aria-label="بستن"
                      className="drawer-close"
                      onClick={() => setReviewMode(null)}
                      type="button"
                    >
                      ×
                    </button>
                  </div>

                  {reviewMode === "MODIFY" ? (
                    <>
                      <label>
                        <span>طبقه‌بندی نهایی</span>
                        <select
                          onChange={(event) =>
                            setReviewClassification(
                              event.target.value as OutcomeClassification,
                            )
                          }
                          value={reviewClassification}
                        >
                          {reviewableClassifications.map((item) => (
                            <option key={item} value={item}>
                              {classificationLabels[item]}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span>خلاصه تغییر مشاهده‌شده</span>
                        <textarea
                          maxLength={4000}
                          onChange={(event) =>
                            setReviewSummary(event.target.value)
                          }
                          rows={4}
                          value={reviewSummary}
                        />
                      </label>
                    </>
                  ) : null}

                  <label>
                    <span>دلیل تصمیم مددکار</span>
                    <textarea
                      maxLength={1000}
                      onChange={(event) => setReviewReason(event.target.value)}
                      rows={3}
                      value={reviewReason}
                    />
                  </label>

                  <div className="outcome-review-form__actions">
                    <Button disabled={busyKey?.startsWith("outcome-")} type="submit">
                      ثبت تصمیم
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => setReviewMode(null)}
                    >
                      انصراف
                    </Button>
                  </div>
                </form>
              ) : null}

              {ready.outcome.status !== "UNDER_REVIEW" ? (
                <div className="outcome-final-state">
                  <Badge tone={outcomeTone(ready.outcome.status)}>
                    تصمیم انسانی ثبت شده
                  </Badge>
                  <strong>
                    {ready.outcome.classification
                      ? classificationLabels[ready.outcome.classification]
                      : ready.outcome.status}
                  </strong>
                  <p>{ready.outcome.observed_change_summary}</p>
                  {ready.outcome.learning_signal_id ? (
                    <span className="ltr-value">
                      Learning Signal: {ready.outcome.learning_signal_id}
                    </span>
                  ) : null}
                  <span>
                    این Outcome رابطه علّی میان مداخله و تغییر PGOR را ادعا نمی‌کند.
                  </span>
                </div>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </Panel>
  );
}
