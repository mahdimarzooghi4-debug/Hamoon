import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError } from "../api/client";
import {
  getAcceptedFacts,
  getDataSources,
  getHouseholdFacts,
  recordHouseholdFact,
  type AcceptedFact,
  type DataSource,
  type HouseholdFact,
} from "../api/familyData";
import { getHousehold, type HouseholdSummary } from "../api/households";
import { AppLink } from "../app/navigation";
import { Badge, EmptyState, ErrorState, LoadingState, Panel } from "../design-system/components";

type State =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "forbidden" }
  | { kind: "not-found" }
  | { kind: "error" }
  | { kind: "ready"; household: HouseholdSummary; sources: DataSource[]; facts: HouseholdFact[]; accepted: AcceptedFact[] };

const statuses: Record<HouseholdFact["validation_status"], string> = {
  PENDING_VALIDATION: "در انتظار اعتبارسنجی",
  VALIDATED: "اعتبارسنجی‌شده",
  DISPUTED: "مورد اختلاف",
  REJECTED: "ردشده",
  SUPERSEDED: "جایگزین‌شده",
};

const dateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "AUTH_REQUIRED") return "ورود سازمانی معتبر لازم است.";
    if (error.status === 403) return "مجوز ثبت اطلاعات این خانوار را ندارید.";
    if (error.status === 404) return "پرونده یا منبع داده در دسترس نیست.";
    if (error.status === 409) return "اطلاعات پرونده تغییر کرده است؛ صفحه را تازه‌سازی کنید.";
    if (error.code === "INVALID_FACT_VALUE") return "نوع یا مقدار داده با قرارداد سرور سازگار نیست.";
  }
  return "ثبت اطلاعات انجام نشد. پیش از تکرار، فهرست را تازه‌سازی کنید.";
}

export function HouseholdRegistrationPage({ householdId }: { householdId: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [employment, setEmployment] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [sourceDetail, setSourceDetail] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const [household, sources, facts, accepted] = await Promise.all([
        getHousehold(householdId),
        getDataSources(),
        getHouseholdFacts(householdId),
        getAcceptedFacts(householdId),
      ]);
      setState({ kind: "ready", household, sources, facts, accepted });
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || !sourceId || !effectiveFrom || !employment) return;
    const date = new Date(effectiveFrom);
    if (Number.isNaN(date.getTime())) {
      setError("زمان اثر معتبر نیست.");
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const created = await recordHouseholdFact(householdId, {
        fact_type: "EMPLOYMENT_STATUS",
        value_type: "CODE",
        value: employment,
        source_id: sourceId,
        source_detail: sourceDetail.trim() || null,
        effective_from: date.toISOString(),
      });
      setEmployment("");
      setSourceId("");
      setSourceDetail("");
      setEffectiveFrom("");
      setSuccess(`اطلاعات با شناسه ${created.id} ثبت شد و تا بازبینی مددکار، پذیرفته‌شده محسوب نمی‌شود.`);
      await refresh();
    } catch (cause: unknown) {
      setError(errorMessage(cause));
      await refresh();
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  if (state.kind === "loading") return <LoadingState label="در حال دریافت پرونده…" />;
  if (state.kind === "auth-required") return <EmptyState title="ورود سازمانی لازم است" description="برای ثبت اطلاعات باید وارد سامانه شوید." />;
  if (state.kind === "forbidden") return <ErrorState title="دسترسی مجاز نیست" description="مجوز ثبت اطلاعات این خانوار وجود ندارد." />;
  if (state.kind === "not-found") return <ErrorState title="پرونده در دسترس نیست" description="پرونده یا منبع داده پیدا نشد." />;
  if (state.kind === "error") return <ErrorState description="اطلاعات پرونده دریافت نشد." />;

  const existingEmployment = state.accepted.find((fact) => fact.fact_type === "EMPLOYMENT_STATUS");
  const recentFacts = [...state.facts].sort((a, b) => b.recorded_at.localeCompare(a.recorded_at)).slice(0, 8);

  return (
    <div className="page-stack" dir="rtl">
      <header className="page-heading">
        <div>
          <AppLink className="text-link" to={`/households/${householdId}`}>بازگشت به پرونده ←</AppLink>
          <span className="eyebrow">ثبت اطلاعات واقعی · پرونده {state.household.case_code}</span>
          <h1>ثبت اطلاعات خانوار</h1>
          <p>فقط اطلاعات مشاهده‌شده یا اعلام‌شده را ثبت کنید. مورد نامعلوم را حدس نزنید.</p>
        </div>
        <Badge tone="warning">بازبینی انسانی لازم است</Badge>
      </header>

      <div className="inline-alert" role="note">
        این فرم فعلاً فقط وضعیت اشتغال در سطح خانوار را ثبت می‌کند. اطلاعات فردی و شاخص‌های دیگر تا تعریف و تأیید قرارداد داده اضافه نمی‌شوند.
      </div>

      {error ? <div className="inline-alert" role="alert">{error}</div> : null}
      {success ? <div className="evidence-success" role="status">{success}</div> : null}

      <Panel>
        <div className="section-heading">
          <div><span className="eyebrow">اطلاعات پایه</span><h2>وضعیت اشتغال خانوار</h2></div>
          <Badge tone="accent">ثبت اولیه</Badge>
        </div>
        {existingEmployment ? (
          <div className="inline-alert">
            برای این پرونده وضعیت اشتغال پذیرفته‌شده وجود دارد. مقدار تازه را از مسیر اصلاح اطلاعات ثبت کنید.
            {" "}<AppLink className="text-link" to={`/households/${householdId}/facts`}>رفتن به اصلاح اطلاعات ←</AppLink>
          </div>
        ) : (
          <form className="fact-form" onSubmit={(event) => void submit(event)}>
            <label className="fact-field">وضعیت اشتغال
              <select required value={employment} disabled={busy} onChange={(event) => setEmployment(event.target.value)}>
                <option value="">انتخاب کنید</option>
                <option value="EMPLOYED">حداقل یک عضو خانوار شاغل است</option>
                <option value="UNEMPLOYED">هیچ‌یک از اعضای خانوار شاغل نیستند</option>
              </select>
            </label>
            <label className="fact-field">منبع اطلاعات
              <select required value={sourceId} disabled={busy} onChange={(event) => setSourceId(event.target.value)}>
                <option value="">منبع را انتخاب کنید</option>
                {state.sources.map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}
              </select>
            </label>
            <label className="fact-field">توضیح منبع <span>(اختیاری)</span>
              <input value={sourceDetail} disabled={busy} onChange={(event) => setSourceDetail(event.target.value)} maxLength={500} />
            </label>
            <label className="fact-field">از چه زمانی این اطلاعات معتبر است؟
              <input required type="datetime-local" value={effectiveFrom} disabled={busy} onChange={(event) => setEffectiveFrom(event.target.value)} />
            </label>
            <p className="muted-copy">ثبت اولیه فقط یک واقعیت در انتظار اعتبارسنجی می‌سازد؛ داده پذیرفته‌شده و آموزش مدل به‌طور خودکار تغییر نمی‌کند.</p>
            <button className="hm-button hm-button--primary" type="submit" disabled={busy || state.sources.length === 0}>
              {busy ? "در حال ثبت…" : "ثبت برای بازبینی"}
            </button>
          </form>
        )}
      </Panel>

      <Panel>
        <div className="section-heading">
          <div><span className="eyebrow">ردپای ثبت</span><h2>اطلاعات ثبت‌شده اخیر</h2></div>
          <AppLink className="text-link" to={`/households/${householdId}/facts`}>بازبینی و اعتبارسنجی ←</AppLink>
        </div>
        {recentFacts.length === 0 ? (
          <EmptyState title="هنوز اطلاعاتی ثبت نشده" description="اطلاعات ثبت‌شده برای این پرونده پس از ذخیره در این بخش دیده می‌شود." />
        ) : (
          <div className="fact-history">
            {recentFacts.map((fact) => (
              <article className="fact-history__item" key={fact.id}>
                <strong>{fact.fact_type}</strong>
                <span>{typeof fact.value === "string" ? fact.value : JSON.stringify(fact.value)}</span>
                <Badge tone={fact.validation_status === "VALIDATED" ? "success" : "warning"}>
                  {statuses[fact.validation_status]}
                </Badge>
                <small>{dateTime.format(new Date(fact.recorded_at))}</small>
              </article>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
