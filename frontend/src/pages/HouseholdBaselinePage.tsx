import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import {
  acceptAssessmentObservation,
  changeAssessmentObservationValidation,
  getAssessment,
  getAssessmentReadiness,
  getAssessmentWorkspace,
  getActivePGORDefinition,
  listDataSources,
  recordAssessmentObservation,
  startBaselineAssessment,
  type AssessmentData,
  type AssessmentReadiness,
  type AssessmentWorkspace,
  type AssessmentWorkspaceIndicator,
  type DataSource,
  type PGORActiveDefinition,
} from "../api/measurement";
import { getHousehold, getHouseholdTimeline, type HouseholdSummary } from "../api/households";
import { AppLink } from "../app/navigation";
import { Badge, EmptyState, ErrorState, LoadingState, Panel } from "../design-system/components";

type State =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "forbidden" }
  | { kind: "not-found" }
  | { kind: "error" }
  | { kind: "ready"; household: HouseholdSummary; sources: DataSource[]; definition: PGORActiveDefinition; assessment: AssessmentData | null; workspace: AssessmentWorkspace | null; readiness: AssessmentReadiness | null };

const dateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { dateStyle: "medium", timeStyle: "short" });

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "AUTH_REQUIRED") return "ورود سازمانی معتبر لازم است.";
    if (error.status === 403) return "مجوز ارزیابی این خانوار را ندارید.";
    if (error.status === 404) return "پرونده یا تعریف فعال PGOR پیدا نشد.";
    if (error.status === 409) return "ارزیابی هم‌زمان تغییر کرده است؛ اطلاعات را تازه‌سازی کنید.";
  }
  return "عملیات ارزیابی انجام نشد. اطلاعات را تازه‌سازی کنید.";
}

export function HouseholdBaselinePage({ householdId }: { householdId: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [scores, setScores] = useState<Record<string, string>>({});
  const [sources, setSources] = useState<Record<string, string>>({});
  const [sourceDetails, setSourceDetails] = useState<Record<string, string>>({});
  const [effectiveTimes, setEffectiveTimes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const [household, dataSources, definition, timeline] = await Promise.all([
        getHousehold(householdId),
        listDataSources(),
        getActivePGORDefinition(),
        getHouseholdTimeline(householdId),
      ]);
      const baseline = timeline
        .filter((item) => item.kind === "ASSESSMENT" && item.detail === "BASELINE" && item.status !== "CANCELLED")
        .sort((left, right) => right.occurred_at.localeCompare(left.occurred_at))[0];
      if (!baseline) {
        setState({ kind: "ready", household, sources: dataSources, definition, assessment: null, workspace: null, readiness: null });
        return;
      }
      const assessment = await getAssessment(baseline.entity_id);
      const [workspace, readiness] = await Promise.all([
        getAssessmentWorkspace(assessment.id),
        getAssessmentReadiness(assessment.id),
      ]);
      setState({ kind: "ready", household, sources: dataSources, definition, assessment, workspace, readiness });
    } catch (cause: unknown) {
      if (cause instanceof ApiError && cause.code === "AUTH_REQUIRED") setState({ kind: "auth-required" });
      else if (cause instanceof ApiError && cause.status === 403) setState({ kind: "forbidden" });
      else if (cause instanceof ApiError && cause.status === 404) setState({ kind: "not-found" });
      else setState({ kind: "error" });
    }
  }, [householdId]);

  useEffect(() => {
    setState({ kind: "loading" });
    void refresh();
  }, [refresh]);

  async function run(key: string, action: () => Promise<void>, message: string) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(key);
    setError(null);
    setSuccess(null);
    try {
      await action();
      setSuccess(message);
      await refresh();
    } catch (cause: unknown) {
      setError(errorMessage(cause));
      await refresh();
    } finally {
      inFlight.current = false;
      setBusy(null);
    }
  }

  async function startBaseline() {
    if (state.kind !== "ready" || inFlight.current) return;
    inFlight.current = true;
    setBusy("start");
    setError(null);
    setSuccess(null);
    try {
      const assessment = await startBaselineAssessment(householdId, state.definition.id);
      const [workspace, readiness] = await Promise.all([
        getAssessmentWorkspace(assessment.id),
        getAssessmentReadiness(assessment.id),
      ]);
      setState({ ...state, assessment, workspace, readiness });
      setSuccess("ارزیابی پایه ایجاد شد؛ ثبت مشاهدات از اینجا آغاز می‌شود.");
    } catch (cause: unknown) {
      setError(errorMessage(cause));
      await refresh();
    } finally {
      inFlight.current = false;
      setBusy(null);
    }
  }

  function record(indicator: AssessmentWorkspaceIndicator) {
    if (state.kind !== "ready" || !state.assessment) return;
    const raw = scores[indicator.id]?.trim() ?? "";
    const sourceId = sources[indicator.id] ?? "";
    const effective = effectiveTimes[indicator.id] ?? "";
    const numericScore = Number(raw);
    if (!raw || !Number.isFinite(numericScore) || numericScore < indicator.score_min || numericScore > indicator.score_max || !sourceId || !effective) {
      setError(`برای «${indicator.name_fa}» امتیاز بین ${indicator.score_min} تا ${indicator.score_max}، منبع و زمان اثر را وارد کنید.`);
      return;
    }
    const effectiveAt = new Date(effective);
    if (Number.isNaN(effectiveAt.getTime())) {
      setError("زمان اثر معتبر نیست.");
      return;
    }
    void run(indicator.id, () => recordAssessmentObservation(state.assessment!.id, {
      indicatorId: indicator.id,
      rawScore: numericScore,
      sourceId,
      sourceDetail: (sourceDetails[indicator.id] ?? "").trim() || null,
      effectiveAt: effectiveAt.toISOString(),
    }), "مشاهده ثبت شد و برای اعتبارسنجی انسانی در انتظار است.");
  }

  function review(indicator: AssessmentWorkspaceIndicator, status: "VALIDATED" | "DISPUTED" | "REJECTED") {
    if (state.kind !== "ready" || !state.assessment || !indicator.latest_observation) return;
    void run(indicator.id, () => changeAssessmentObservationValidation(state.assessment!.id, indicator.latest_observation!, status), "وضعیت بازبینی ذخیره شد.");
  }

  function accept(indicator: AssessmentWorkspaceIndicator) {
    if (state.kind !== "ready" || !state.assessment || !indicator.latest_observation) return;
    void run(indicator.id, () => acceptAssessmentObservation(state.assessment!.id, indicator.id, indicator.latest_observation!), "مشاهده به‌صورت صریح پذیرفته شد.");
  }

  if (state.kind === "loading") return <LoadingState label="در حال دریافت تعریف PGOR و پرونده…" />;
  if (state.kind === "auth-required") return <EmptyState title="ورود سازمانی لازم است" description="برای ثبت ارزیابی باید وارد سامانه شوید." />;
  if (state.kind === "forbidden") return <ErrorState title="دسترسی مجاز نیست" description="مجوز ارزیابی این خانوار وجود ندارد." />;
  if (state.kind === "not-found") return <ErrorState title="پرونده یا تعریف ارزیابی پیدا نشد" description="تعریف فعال PGOR یا پرونده در دسترس نیست." />;
  if (state.kind === "error") return <ErrorState description="اطلاعات ارزیابی دریافت نشد." />;

  const indicators = state.workspace?.indicators ?? [];
  const requirementUnresolved = state.definition.requirement_policy_status === "UNRESOLVED";
  const validationStatus = state.readiness?.status ?? null;

  return (
    <div className="page-stack" dir="rtl">
      <header className="page-heading">
        <div>
          <AppLink className="text-link" to={`/households/${householdId}`}>بازگشت به پرونده ←</AppLink>
          <span className="eyebrow">ارزیابی پایه · پرونده {state.household.case_code}</span>
          <h1>ثبت خط مبنای خانوار</h1>
          <p>امتیاز هر شاخص باید بر اساس مشاهده و منبع ثبت شود؛ محاسبه رسمی تا تکمیل سیاست و بازبینی مجاز نیست.</p>
        </div>
        <Badge tone="warning">بدون تصمیم خودکار</Badge>
      </header>

      {error ? <div className="inline-alert" role="alert">{error}</div> : null}
      {success ? <div className="evidence-success" role="status">{success}</div> : null}

      <Panel>
        <div className="section-heading">
          <div><span className="eyebrow">{state.definition.code} · نسخه {state.definition.version}</span><h2>تعریف فعال شاخص‌ها</h2></div>
          <Badge tone={requirementUnresolved ? "warning" : "accent"}>{requirementUnresolved ? "سیاست تکمیل شاخص‌ها تعیین نشده" : state.definition.requirement_policy_status}</Badge>
        </div>
        {state.assessment ? (
          <div className="summary-card">
            <strong>ارزیابی پایه {state.assessment.status === "CANCELLED" ? "لغو شده" : "فعال"}</strong>
            <span>شروع: {dateTime.format(new Date(state.assessment.started_at))}</span>
            {validationStatus ? <span>آمادگی: {validationStatus}</span> : null}
          </div>
        ) : (
          <div>
            <p>ابتدا ارزیابی پایه‌ای با نسخهٔ فعال تعریف PGOR ساخته می‌شود. این کار به‌تنهایی امتیاز یا پیشنهاد خودکار ایجاد نمی‌کند.</p>
            <button className="hm-button hm-button--primary" type="button" disabled={busy !== null} onClick={() => void startBaseline()}>
              {busy === "start" ? "در حال شروع…" : "شروع ارزیابی پایه"}
            </button>
          </div>
        )}
      </Panel>

      {state.assessment && indicators.length === 0 ? (
        <EmptyState title="شاخصی در تعریف فعال نیست" description="برای این ارزیابی امکان ثبت مشاهده وجود ندارد." />
      ) : null}

      {indicators.map((indicator) => {
        const observation = indicator.latest_observation;
        const pending = observation?.validation_status === "PENDING_VALIDATION";
        const validated = observation?.validation_status === "VALIDATED";
        return (
          <Panel key={indicator.id}>
            <div className="section-heading">
              <div>
                <span className="eyebrow">{indicator.variable_code} · {indicator.dimension_name_fa}</span>
                <h2>{indicator.name_fa}</h2>
              </div>
              <Badge tone={observation?.accepted ? "success" : observation ? "warning" : "neutral"}>
                {observation?.accepted ? "پذیرفته‌شده" : observation?.validation_status ?? "ثبت‌نشده"}
              </Badge>
            </div>
            {observation ? (
              <div className="fact-current">
                <div><span>امتیاز</span><strong>{Number(observation.raw_score_0_100).toLocaleString("fa-IR")}</strong></div>
                <div><span>منبع</span><strong>{state.sources.find((source) => source.id === observation.source_id)?.name ?? observation.source_id}</strong></div>
                <div><span>زمان اثر</span><strong>{dateTime.format(new Date(observation.effective_at))}</strong></div>
              </div>
            ) : null}
            {observation && pending ? (
              <div className="fact-actions">
                <button className="hm-button hm-button--secondary" type="button" disabled={busy !== null} onClick={() => review(indicator, "VALIDATED")}>تأیید مشاهده</button>
                <button className="hm-button hm-button--secondary" type="button" disabled={busy !== null} onClick={() => review(indicator, "DISPUTED")}>ثبت اختلاف</button>
                <button className="hm-button hm-button--secondary" type="button" disabled={busy !== null} onClick={() => review(indicator, "REJECTED")}>رد مشاهده</button>
              </div>
            ) : null}
            {observation && validated && !observation.accepted ? (
              <button className="hm-button hm-button--secondary" type="button" disabled={busy !== null} onClick={() => accept(indicator)}>پذیرش صریح این مشاهده</button>
            ) : null}
            {state.assessment && !observation ? (
              <form className="fact-form" onSubmit={(event) => { event.preventDefault(); record(indicator); }}>
                <label className="fact-field">امتیاز ({indicator.score_min} تا {indicator.score_max})
                  <input type="number" min={indicator.score_min} max={indicator.score_max} step="0.01" value={scores[indicator.id] ?? ""} disabled={busy !== null} onChange={(event) => setScores((current) => ({ ...current, [indicator.id]: event.target.value }))} />
                </label>
                <label className="fact-field">منبع مشاهده
                  <select value={sources[indicator.id] ?? ""} disabled={busy !== null} onChange={(event) => setSources((current) => ({ ...current, [indicator.id]: event.target.value }))}>
                    <option value="">منبع را انتخاب کنید</option>
                    {state.sources.map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}
                  </select>
                </label>
                <label className="fact-field">شرح منبع <span>(اختیاری)</span>
                  <input maxLength={500} value={sourceDetails[indicator.id] ?? ""} disabled={busy !== null} onChange={(event) => setSourceDetails((current) => ({ ...current, [indicator.id]: event.target.value }))} />
                </label>
                <label className="fact-field">زمان اثر
                  <input type="datetime-local" value={effectiveTimes[indicator.id] ?? ""} disabled={busy !== null} onChange={(event) => setEffectiveTimes((current) => ({ ...current, [indicator.id]: event.target.value }))} />
                </label>
                <button className="hm-button hm-button--primary" type="submit" disabled={busy !== null}>{busy === indicator.id ? "در حال ثبت…" : "ثبت مشاهده برای بازبینی"}</button>
              </form>
            ) : null}
            {observation?.accepted ? <p className="muted-copy">این مشاهده با تصمیم انسانی پذیرفته شده است.</p> : null}
          </Panel>
        );
      })}

      {requirementUnresolved ? (
        <div className="inline-alert">سیاست رسمی کامل‌بودن ارزیابی هنوز تعیین نشده است؛ این صفحه محاسبهٔ رسمی PGOR را اجرا نمی‌کند.</div>
      ) : null}
    </div>
  );
}
