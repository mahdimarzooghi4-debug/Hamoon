import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { ApiError } from "../api/client";
import {
  changeFactValidation,
  getAcceptedFacts,
  getDataSources,
  getHouseholdFacts,
  recordHouseholdFact,
  resolveAcceptedFact,
  type AcceptedFact,
  type DataSource,
  type FactValueType,
  type HouseholdFact,
  type ValidationStatus,
} from "../api/familyData";
import { getHousehold, type HouseholdSummary } from "../api/households";
import { AppLink } from "../app/navigation";
import { Badge, Button, EmptyState, ErrorState, LoadingState, Panel } from "../design-system/components";

type DataState =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "forbidden" }
  | { kind: "not-found" }
  | { kind: "error" }
  | { kind: "ready"; household: HouseholdSummary; sources: DataSource[]; facts: HouseholdFact[]; accepted: AcceptedFact[] };

const validationLabels: Record<ValidationStatus, string> = {
  PENDING_VALIDATION: "در انتظار اعتبارسنجی",
  VALIDATED: "اعتبارسنجی‌شده",
  DISPUTED: "مورد اختلاف",
  REJECTED: "ردشده",
  SUPERSEDED: "جایگزین‌شده",
};

const valueLabels: Record<FactValueType, string> = {
  STRING: "متن", CODE: "کد", NUMBER: "عدد", BOOLEAN: "بله / خیر",
  DATE: "تاریخ", DATETIME: "تاریخ و زمان با منطقه زمانی",
  RANGE: "بازه ساخت‌یافته", JSON_STRUCTURED: "داده ساخت‌یافته",
};

const reasons = [
  ["DATA_ENTRY_ERROR", "اشتباه ورود داده"],
  ["HOUSEHOLD_CORRECTION", "اعلام اشتباه توسط خانوار"],
  ["FIELD_OBSERVATION", "مشاهده میدانی"],
  ["SOURCE_CONFLICT", "تعارض با منبع رسمی"],
  ["NEW_EVIDENCE", "مدرک جدید"],
  ["OTHER", "سایر"],
] as const;

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "نامشخص";
  if (typeof value === "boolean") return value ? "بله" : "خیر";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function parseValue(valueType: FactValueType, raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) throw new Error("مقدار صحیح را وارد کنید؛ مقدار نامعلوم نباید حدس زده شود.");
  if (valueType === "BOOLEAN") {
    if (trimmed !== "true" && trimmed !== "false") throw new Error("مقدار بله یا خیر را انتخاب کنید.");
    return trimmed === "true";
  }
  if (valueType === "NUMBER") {
    const value = Number(trimmed);
    if (!Number.isFinite(value) || Math.abs(value) > Number.MAX_SAFE_INTEGER) {
      throw new Error("عدد خارج از محدوده امن مرورگر است؛ مقدار دقیق را از مسیر مجاز ثبت کنید.");
    }
    return value;
  }
  if (valueType === "DATE") {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed) || Number.isNaN(Date.parse(trimmed))) {
      throw new Error("تاریخ را با قالب YYYY-MM-DD وارد کنید.");
    }
    return trimmed;
  }
  if (valueType === "DATETIME") {
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(trimmed) || Number.isNaN(Date.parse(trimmed))) {
      throw new Error("زمان باید ISO 8601 با منطقه زمانی صریح باشد.");
    }
    return trimmed;
  }
  if (valueType === "RANGE" || valueType === "JSON_STRUCTURED") {
    let value: unknown;
    try { value = JSON.parse(trimmed); } catch { throw new Error("ساختار JSON معتبر نیست."); }
    if (valueType === "RANGE" && (
      typeof value !== "object" || value === null || Array.isArray(value)
      || (!("min" in value) && !("max" in value))
    )) throw new Error("بازه باید شیء JSON دارای min یا max باشد.");
    if (valueType === "JSON_STRUCTURED" && (
      typeof value !== "object" || value === null
    )) throw new Error("داده ساخت‌یافته باید شیء یا آرایه JSON باشد.");
    return value;
  }
  return trimmed;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "VERSION_CONFLICT" || error.status === 409) {
      return "نسخه داده تغییر کرده است. اطلاعات را تازه‌سازی و تصمیم را مجدداً بررسی کنید.";
    }
    if (error.code === "FACT_NOT_VALIDATED") return "فقط واقعیت اعتبارسنجی‌شده قابل انتخاب به‌عنوان داده پذیرفته‌شده است.";
    if (error.code === "INVALID_FACT_VALIDATION_TRANSITION") return "این تغییر وضعیت مجاز نیست؛ تاریخچه را تازه‌سازی کنید.";
    if (error.code === "DATA_SOURCE_NOT_FOUND") return "منبع انتخاب‌شده فعال یا معتبر نیست؛ فهرست منابع را تازه‌سازی کنید.";
    if (error.status === 403 || error.status === 404) return "مجوز یا پرونده در دسترس نیست.";
    if (error.code === "INVALID_FACT_VALUE") return "نوع و مقدار داده با قرارداد سرور سازگار نیست.";
    if (error.code === "AUTH_REQUIRED") return "ورود سازمانی معتبر لازم است.";
  }
  if (error instanceof Error && !(error instanceof ApiError)) return error.message;
  return "نتیجه عملیات نامشخص است. پیش از تکرار، داده‌ها را تازه‌سازی کنید.";
}

const dateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { dateStyle: "medium", timeStyle: "short" });

export function HouseholdFactsPage({ householdId }: { householdId: string }) {
  const [state, setState] = useState<DataState>({ kind: "loading" });
  const [selectedType, setSelectedType] = useState("");
  const [rawValue, setRawValue] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [sourceDetail, setSourceDetail] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [reasonCode, setReasonCode] = useState("");
  const [reasonText, setReasonText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmResolve, setConfirmResolve] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [household, sources, facts, accepted] = await Promise.all([
        getHousehold(householdId), getDataSources(), getHouseholdFacts(householdId), getAcceptedFacts(householdId),
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
    setSelectedType("");
    setRawValue("");
    setSourceId("");
    setReasonCode("");
    setReasonText("");
    void refresh();
  }, [refresh]);

  const accepted = state.kind === "ready" ? state.accepted : [];
  const facts = state.kind === "ready" ? state.facts : [];
  const current = accepted.find((item) => item.fact_type === selectedType);
  const oldFact = facts.find((item) => item.id === current?.fact_id);
  const selectedFacts = useMemo(
    () => facts.filter((item) => item.fact_type === selectedType)
      .sort((a, b) => b.recorded_at.localeCompare(a.recorded_at)),
    [facts, selectedType],
  );
  const canRecord = Boolean(current && oldFact && sourceId && reasonCode && reasonText.trim() && effectiveFrom.trim() && rawValue.trim());
  const canReview = Boolean(reasonCode && reasonText.trim());

  async function run(action: () => Promise<string>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const message = await action();
      setSuccess(message);
      await refresh();
    } catch (cause: unknown) {
      setError(errorMessage(cause));
      await refresh();
    } finally {
      setBusy(false);
      setConfirmResolve(false);
    }
  }

  function submitRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canRecord || !oldFact || !current) return;
    const parsed = (() => { try { return { value: parseValue(oldFact.value_type, rawValue) }; } catch (cause) { setError(errorMessage(cause)); return null; } })();
    if (!parsed) return;
    void run(async () => {
      const created = await recordHouseholdFact(householdId, {
        fact_type: current.fact_type,
        value_type: oldFact.value_type,
        value: parsed.value,
        source_id: sourceId,
        source_detail: sourceDetail.trim() || null,
        effective_from: effectiveFrom.trim(),
      });
      setRawValue("");
      return "واقعیت جدید با شناسه " + created.id + " در انتظار اعتبارسنجی ثبت شد؛ داده پذیرفته‌شده تغییری نکرده است.";
    });
  }

  if (state.kind === "loading") return <LoadingState label="در حال دریافت واقعیت‌ها و داده پذیرفته‌شده…" />;
  if (state.kind === "auth-required") return <EmptyState title="ورود سازمانی لازم است" description="بدون ورود معتبر، داده خانوار قابل مشاهده نیست." />;
  if (state.kind === "forbidden") return <ErrorState title="دسترسی مجاز نیست" description="مجوز مشاهده و اصلاح این خانوار وجود ندارد." />;
  if (state.kind === "not-found") return <ErrorState title="پرونده در دسترس نیست" description="پرونده پیدا نشد." />;
  if (state.kind === "error") return <ErrorState description="داده خانوار دریافت نشد." action={<Button variant="secondary" onClick={() => void refresh()}>تلاش دوباره</Button>} />;

  return (
    <div className="page-stack fact-page">
      <header className="page-heading">
        <div>
          <AppLink className="text-link" to={"/households/" + householdId}>بازگشت به پرونده ←</AppLink>
          <span className="eyebrow">اصلاح داده خانوار · نگاشت فیگما 37:5908 / 37:6098 / 37:6288 / 37:6493</span>
          <h1>اصلاح و اعتبارسنجی اطلاعات</h1>
          <p>پرونده {state.household.case_code} · داده پیشین حفظ می‌شود و هیچ مقدار جدیدی خودکار پذیرفته نمی‌شود.</p>
        </div>
        <Badge tone="accent">تصمیم انسانی</Badge>
      </header>

      <div className="fact-steps" aria-label="مراحل اصلاح">
        <span>۱. انتخاب داده پذیرفته‌شده</span>
        <span>۲. ثبت مقدار و منبع جدید</span>
        <span>۳. اعتبارسنجی و انتخاب صریح</span>
      </div>

      {error ? <div className="inline-alert" role="alert">{error}</div> : null}
      {success ? <div className="evidence-success" role="status">{success}</div> : null}

      <Panel>
        <div className="section-heading"><div><span className="eyebrow">داده واقعی و فعلی</span><h2>انتخاب نوع واقعیت</h2></div><Button variant="secondary" disabled={busy} onClick={() => void refresh()}>تازه‌سازی</Button></div>
        {accepted.length === 0 ? (
          <EmptyState title="هنوز داده پذیرفته‌شده وجود ندارد" description="این صفحه برای اصلاح واقعیت‌های پذیرفته‌شده است؛ هیچ نوع یا مقدار فرضی ایجاد نمی‌شود." />
        ) : (
          <label className="fact-field">نوع واقعیت
            <select value={selectedType} disabled={busy} onChange={(event) => { setSelectedType(event.target.value); setRawValue(""); setConfirmResolve(false); }}>
              <option value="">یک داده پذیرفته‌شده انتخاب کنید</option>
              {accepted.map((item) => <option key={item.fact_type} value={item.fact_type}>{item.fact_type}</option>)}
            </select>
          </label>
        )}
        {current ? (
          <div className="fact-current">
            <div><span>مقدار پذیرفته‌شده فعلی</span><strong>{formatValue(current.accepted_value)}</strong></div>
            <div><span>منبع</span><strong>{state.sources.find((item) => item.id === current.source_id)?.name ?? current.source_id}</strong></div>
            <div><span>نسخه Projection</span><strong>{current.projection_version.toLocaleString("fa-IR")}</strong></div>
            <div><span>تاریخ اثر</span><strong>{dateTime.format(new Date(current.effective_from))}</strong></div>
          </div>
        ) : null}
        {current && !oldFact ? <div className="inline-alert" role="alert">واقعیت اصلی برای تعیین نوع مقدار در دسترس نیست؛ ثبت اصلاح مسدود است.</div> : null}
      </Panel>

      {current && oldFact ? (
        <Panel className="fact-entry-panel">
          <div className="section-heading"><div><span className="eyebrow">ثبت نسخه مستقل، بدون حذف داده قبلی</span><h2>مقدار صحیح و مبنای اصلاح</h2></div><Badge tone="warning">ثبت اولیه = انتظار اعتبارسنجی</Badge></div>
          <form className="fact-form" onSubmit={submitRecord}>
            <div className="fact-two-col">
              <div className="fact-readonly"><span>مقدار قبلی</span><strong>{formatValue(current.accepted_value)}</strong></div>
              <label className="fact-field">مقدار پیشنهادی جدید · {valueLabels[oldFact.value_type]}
                {oldFact.value_type === "BOOLEAN" ? (
                  <select required disabled={busy} value={rawValue} onChange={(event) => setRawValue(event.target.value)}>
                    <option value="">انتخاب کنید</option><option value="true">بله</option><option value="false">خیر</option>
                  </select>
                ) : oldFact.value_type === "RANGE" || oldFact.value_type === "JSON_STRUCTURED" ? (
                  <textarea required rows={3} value={rawValue} disabled={busy} onChange={(event) => setRawValue(event.target.value)} placeholder='{"min": 1, "max": 2}' />
                ) : (
                  <input required dir="ltr" type={oldFact.value_type === "DATE" ? "date" : oldFact.value_type === "NUMBER" ? "number" : "text"}
                    step={oldFact.value_type === "NUMBER" ? "any" : undefined}
                    value={rawValue} disabled={busy} onChange={(event) => setRawValue(event.target.value)}
                    placeholder={oldFact.value_type === "DATETIME" ? "2026-10-25T10:30:00+03:30" : "مقدار مستند و واقعی"} />
                )}
              </label>
            </div>
            <div className="fact-two-col">
              <label className="fact-field">منبع فعال داده
                <select required value={sourceId} disabled={busy} onChange={(event) => setSourceId(event.target.value)}>
                  <option value="">منبع را انتخاب کنید</option>
                  {state.sources.map((source) => <option key={source.id} value={source.id}>{source.name} · {source.code}</option>)}
                </select>
              </label>
              <label className="fact-field">تاریخ اثر · ISO 8601 با منطقه زمانی
                <input required dir="ltr" type="text" value={effectiveFrom} disabled={busy} onChange={(event) => setEffectiveFrom(event.target.value)} placeholder="2026-10-25T10:30:00+03:30" />
              </label>
            </div>
            <label className="fact-field">جزئیات منبع (اختیاری)
              <input maxLength={500} value={sourceDetail} disabled={busy} onChange={(event) => setSourceDetail(event.target.value)} placeholder="شناسه استعلام یا توضیح قابل پیگیری؛ بدون ادعای تأیید مدرک" />
            </label>
            <div className="fact-reason-block">
              <strong>دلیل اصلاح و بازبینی انسانی</strong>
              <p>کدهای زیر فقط برچسب‌های ثبت دلیل در رابط کاربری‌اند؛ اعتبار داده را خودکار تعیین نمی‌کنند.</p>
              <div className="fact-reason-options">
                {reasons.map(([code, label]) => <button key={code} type="button" disabled={busy} aria-pressed={reasonCode === code} className={reasonCode === code ? "evidence-filter is-active" : "evidence-filter"} onClick={() => setReasonCode(code)}>{label}</button>)}
              </div>
              <label className="fact-field">توضیح مستند دلیل
                <textarea required maxLength={1000} rows={2} value={reasonText} disabled={busy} onChange={(event) => setReasonText(event.target.value)} placeholder="توضیح واقعی تصمیم مددکار" />
              </label>
            </div>
            <p className="fact-caution">ثبت، صرفاً یک واقعیت جدید با وضعیت PENDING_VALIDATION می‌سازد. تأیید یا تغییر Accepted State به اقدام انسانی جداگانه نیاز دارد.</p>
            <Button type="submit" disabled={busy || !canRecord}>{busy ? "در حال ثبت…" : "ثبت واقعیت در انتظار بررسی"}</Button>
          </form>
        </Panel>
      ) : null}

      {current ? (
        <Panel>
          <div className="section-heading"><div><span className="eyebrow">تاریخچه قابل ممیزی</span><h2>نسخه‌ها و تصمیم‌های اعتبارسنجی</h2></div><Badge tone="accent">{selectedFacts.length.toLocaleString("fa-IR")} واقعیت</Badge></div>
          <p className="fact-caution">اعتبارسنجی و انتخاب داده پذیرفته‌شده دو عملیات مستقل هستند. نسخه پیشین در تاریخچه باقی می‌ماند؛ این صفحه آن را خودکار SUPERSEDED نمی‌کند.</p>
          {selectedFacts.length === 0 ? <EmptyState title="واقعیتی ثبت نشده" description="برای این نوع داده، تاریخچه‌ای در دسترس نیست." /> : (
            <div className="fact-history">
              {selectedFacts.map((fact) => {
                const isCurrent = fact.id === current.fact_id;
                const canValidate = fact.validation_status === "PENDING_VALIDATION" || fact.validation_status === "DISPUTED";
                const canResolve = fact.validation_status === "VALIDATED" && !isCurrent;
                return (
                  <article key={fact.id} className="fact-history-item">
                    <div className="fact-history-head">
                      <strong>{formatValue(fact.value)}</strong>
                      <Badge tone={isCurrent ? "success" : canValidate ? "warning" : "neutral"}>{isCurrent ? "داده پذیرفته‌شده فعلی" : validationLabels[fact.validation_status]}</Badge>
                    </div>
                    <div className="fact-history-meta">
                      <span>منبع: {state.sources.find((source) => source.id === fact.source_id)?.name ?? fact.source_id}</span>
                      <span>اثر: {dateTime.format(new Date(fact.effective_from))}</span>
                      <span>ثبت: {dateTime.format(new Date(fact.recorded_at))}</span>
                      <span>نسخه اعتبارسنجی: {fact.validation_version.toLocaleString("fa-IR")}</span>
                    </div>
                    {canValidate ? (
                      <div className="fact-actions">
                        <Button disabled={busy || !canReview} onClick={() => void run(async () => { await changeFactValidation(householdId, fact, "VALIDATED", reasonCode, reasonText.trim()); return "اعتبارسنجی انسانی ثبت شد؛ داده پذیرفته‌شده هنوز تغییر نکرده است."; })}>تأیید اعتبار</Button>
                        <Button variant="secondary" disabled={busy || !canReview} onClick={() => void run(async () => { await changeFactValidation(householdId, fact, "DISPUTED", reasonCode, reasonText.trim()); return "واقعیت مورد اختلاف ثبت شد؛ بررسی انسانی لازم است."; })}>ثبت اختلاف</Button>
                        <Button variant="secondary" disabled={busy || !canReview} onClick={() => void run(async () => { await changeFactValidation(householdId, fact, "REJECTED", reasonCode, reasonText.trim()); return "واقعیت رد شد؛ داده پذیرفته‌شده تغییر نکرد."; })}>رد واقعیت</Button>
                      </div>
                    ) : null}
                    {canResolve ? (
                      <div className="fact-resolve">
                        <label><input type="checkbox" checked={confirmResolve} disabled={busy} onChange={(event) => setConfirmResolve(event.target.checked)} /> انتخاب این واقعیت به‌عنوان Accepted State را آگاهانه تأیید می‌کنم.</label>
                        <Button disabled={busy || !canReview || !confirmResolve} onClick={() => void run(async () => {
                          await resolveAcceptedFact(householdId, fact, current.projection_version, reasonCode, reasonText.trim());
                          return "داده پذیرفته‌شده با تصمیم صریح انسانی و نسخه مورد انتظار به‌روزرسانی شد.";
                        })}>انتخاب صریح به‌عنوان داده پذیرفته‌شده</Button>
                      </div>
                    ) : null}
                    <small className="ltr-value">شناسه واقعیت: {fact.id}</small>
                  </article>
                );
              })}
            </div>
          )}
        </Panel>
      ) : null}
    </div>
  );
}
