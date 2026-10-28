import { useState, type FormEvent } from "react";
import { groups, loadDemoIndicators, type Group } from "./questionBank";
import { addDemoReviewRecords, loadDemoReviewRecords, saveDemoReviewRecords, type MeasurementStatus, type ReviewRecord, type ReviewStatus } from "./observationReviewData";

type DemoEntry = {
  id: string;
  householdRef: string;
  group: Group;
  indicatorId: string;
  indicatorRevision: number;
  indicator: string;
  indicatorGuidance: string;
  score: number | null;
  source: string | null;
  effectiveAt: string;
  measurementStatus: MeasurementStatus;
  measurementNote: string;
  note: string;
  status: ReviewStatus;
};

const entryStatusLabels: Record<ReviewStatus, string> = {
  PENDING: "در انتظار بازبینی",
  ACCEPTED: "تأییدشده",
  RETURNED: "نیازمند اصلاح",
  SUPERSEDED: "جایگزین‌شده",
};

const measurementStatusLabels: Record<MeasurementStatus, string> = {
  SCORED: "قابل امتیازدهی",
  NOT_ASSESSED: "سنجش‌نشده",
  INSUFFICIENT_EVIDENCE: "مدرک ناکافی",
  CONFLICTING: "دادهٔ متعارض",
  NOT_APPLICABLE: "نامربوط",
};

const demoHouseholds = ["HM-1405-021", "HM-1405-018", "HM-1405-014", "HM-1405-009"];

const summaries: Record<Group, string> = {
  P: "شاخص‌های مشارکت خانوار در فرایند تغییر",
  G: "شاخص‌های ظرفیت رشد خانوار",
  O: "شاخص‌های فرصت و دسترسی",
  R: "شاخص‌های تاب‌آوری خانوار",
};

export function FigmaIntakeDemo() {
  const [dimension, setDimension] = useState<Group>("P");
  const [householdRef, setHouseholdRef] = useState("HM-1405-021");
  const [values, setValues] = useState<Record<string, string>>({});
  const [measurementStatuses, setMeasurementStatuses] = useState<Record<string, MeasurementStatus>>({});
  const [measurementNotes, setMeasurementNotes] = useState<Record<string, string>>({});
  const [source, setSource] = useState("");
  const [effectiveAt, setEffectiveAt] = useState("");
  const [entries, setEntries] = useState<DemoEntry[]>(() => loadDemoReviewRecords()
    .filter((record) => record.id.startsWith("field-"))
    .map((record) => ({
      id: record.id,
      householdRef: record.householdRef,
      group: record.group,
      indicatorId: record.indicatorId,
      indicatorRevision: record.indicatorRevision,
      indicator: record.indicator,
      indicatorGuidance: record.indicatorGuidance,
      score: record.score,
      source: record.source,
      effectiveAt: record.effectiveAt,
      measurementStatus: record.measurementStatus,
      measurementNote: record.measurementNote,
      note: record.note,
      status: record.status,
    })),
  );
  const [notice, setNotice] = useState("");
  const [indicators] = useState(loadDemoIndicators);
  const activeDimension = groups.find((item) => item.id === dimension)!;
  const activeIndicators = indicators.filter((item) => item.group === dimension && item.active);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const entered = activeIndicators.filter((item) => {
      const status = measurementStatuses[item.id] ?? "SCORED";
      return status !== "SCORED" || (values[item.id] !== undefined && values[item.id] !== "");
    });
    if (entered.length === 0) {
      setNotice("برای دست‌کم یک شاخص، عدد یا وضعیت سنجش انتخاب کنید.");
      return;
    }
    const scored = entered.filter((item) => (measurementStatuses[item.id] ?? "SCORED") === "SCORED");
    if (scored.some((item) => {
      const value = Number(values[item.id]);
      return values[item.id] === "" || !Number.isFinite(value) || value < 0 || value > 100;
    })) {
      setNotice("عدد هر شاخص قابل امتیازدهی باید بین ۰ تا ۱۰۰ باشد.");
      return;
    }
    if (entered.some((item) => {
      const status = measurementStatuses[item.id] ?? "SCORED";
      return status !== "SCORED" && !measurementNotes[item.id]?.trim();
    })) {
      setNotice("برای شاخصی که امتیاز ندارد، دلیل وضعیت سنجش را بنویسید.");
      return;
    }
    if (scored.length > 0 && !source) {
      setNotice("برای شاخص‌های امتیازدار، منبع داده را انتخاب کنید.");
      return;
    }
    if (!effectiveAt) {
      setNotice("تاریخ سنجش یا اثر را تکمیل کنید.");
      return;
    }
    const completed = entered.map((item, index) => {
      const measurementStatus = measurementStatuses[item.id] ?? "SCORED";
      return {
        id: "field-" + (Date.now() + index),
        householdRef,
        group: dimension,
        indicatorId: item.id,
        indicatorRevision: item.revision,
        indicator: item.category,
        indicatorGuidance: item.guidance,
        score: measurementStatus === "SCORED" ? Number(values[item.id]) : null,
        measurementStatus,
        measurementNote: measurementStatus === "SCORED" ? "" : measurementNotes[item.id].trim(),
        source: measurementStatus === "SCORED" ? source : null,
        effectiveAt,
        note: "ثبت تازه از فرم مددکار؛ در انتظار بازبینی.",
        status: "PENDING" as const,
      };
    });
    const submittedAt = new Date().toISOString().slice(0, 10);
    addDemoReviewRecords(completed.map((entry) => ({
      id: entry.id,
      householdRef: entry.householdRef,
      group: entry.group,
      indicatorId: entry.indicatorId,
      indicatorRevision: entry.indicatorRevision,
      indicator: entry.indicator,
      indicatorGuidance: entry.indicatorGuidance,
      score: entry.score,
      measurementStatus: entry.measurementStatus,
      measurementNote: entry.measurementNote,
      source: entry.source,
      effectiveAt: entry.effectiveAt,
      submittedAt,
      status: "PENDING" as const,
      note: entry.note,
    })));
    setEntries((current) => [...completed.reverse(), ...current]);
    setValues({});
    setMeasurementStatuses({});
    setMeasurementNotes({});
    setSource("");
    setEffectiveAt("");
    setNotice("مقادیر و وضعیت‌های سنجش به صف بازبینی دمو افزوده شدند؛ به سرور ارسال نمی‌شوند.");
  }

  function resubmit(event: FormEvent<HTMLFormElement>, returned: DemoEntry) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const score = Number(formData.get("score"));
    const source = String(formData.get("source") ?? "");
    const effectiveAt = String(formData.get("effectiveAt") ?? "");
    if (!Number.isFinite(score) || score < 0 || score > 100 || !source || !effectiveAt) {
      setNotice("مقدار، منبع و تاریخ اثر را بررسی کنید.");
      return;
    }
    const corrected: ReviewRecord = {
      id: `field-${Date.now()}`,
      householdRef: returned.householdRef,
      group: returned.group,
      indicatorId: returned.indicatorId,
      indicatorRevision: returned.indicatorRevision,
      indicator: returned.indicator,
      indicatorGuidance: returned.indicatorGuidance,
      score,
      measurementStatus: "SCORED",
      measurementNote: "",
      source,
      effectiveAt,
      submittedAt: new Date().toISOString().slice(0, 10),
      status: "PENDING",
      note: `اصلاح‌شده بر اساس نظر بازبین: ${returned.note}`,
      supersedesId: returned.id,
    };
    const history = loadDemoReviewRecords().map((record) =>
      record.id === returned.id ? { ...record, status: "SUPERSEDED" as const } : record,
    );
    saveDemoReviewRecords([corrected, ...history]);
    setEntries((current) => [
      corrected,
      ...current.map((entry) => entry.id === returned.id ? { ...entry, status: "SUPERSEDED" as const } : entry),
    ]);
    setNotice("نسخهٔ اصلاح‌شده به صف بازبینی افزوده شد؛ ثبت برگشتی قبلی در تاریخچه باقی ماند.");
  }

  return (
    <main className="fh-intake" aria-label="دموی ثبت عددی شاخص‌های PGOR" dir="rtl">
      <header className="fh-intake__heading">
        <div>
          <span className="fh-intake__eyebrow">دموی محیط مددکار · پرونده {householdRef}</span>
          <h1>ثبت میدانی داده‌های خانوار</h1>
          <p>مددکار مقدار عددی هر شاخص را همراه منبع و تاریخ ثبت می‌کند؛ این صفحه پرسش‌نامهٔ مصاحبه‌ای نیست.</p>
        </div>
        <span className="fh-intake__badge">نمونهٔ ساختگی</span>
      </header>

      <div className="fh-intake__notice" role="note">
        <strong>دموی بدون اتصال</strong>
        <span>اطلاعات واقعی وارد نکنید. اگر شواهد برای نمره ندارید، صفر ثبت نکنید؛ وضعیت سنجش را با دلیل انتخاب کنید. قاعدهٔ امتیازدهی هنوز نیازمند تأیید تخصصی است.</span>
      </div>

      <div className="fh-intake__grid">
        <section className="fh-intake__card">
          <div className="fh-intake__section-head">
            <div><small>داده‌های سنجش توانمندسازی</small><h2>ثبت عدد زیر دستهٔ PGOR</h2></div>
            <span className="fh-intake__step">گام ۲</span>
          </div>

          <div className="fh-intake__dimensions" role="tablist" aria-label="دسته‌های PGOR">
            {groups.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={dimension === item.id}
                className={dimension === item.id ? "fh-intake__dimension is-active" : "fh-intake__dimension"}
                onClick={() => { setDimension(item.id); setNotice(""); }}
              >
                <strong>{item.id}</strong><span>{item.name}</span>
              </button>
            ))}
          </div>

          <div className="fh-intake__model-note">
            <strong>{activeDimension.id} — {activeDimension.name}</strong>
            <span>{summaries[activeDimension.id]}</span>
            <span>شاخص‌ها از نسخهٔ نمایشی بانک PGOR بارگذاری می‌شوند. راهنماها برای مددکارند و روش امتیازدهی رسمی محسوب نمی‌شوند.</span>
          </div>

          <form onSubmit={submit} className="fh-intake__form">
            <div className="fh-intake__questions">
              {activeIndicators.map((item) => (
                <fieldset className="fh-intake__question" key={item.id}>
                  <legend><strong>{item.category}</strong><small>{item.guidance}</small></legend>
                  <label className="fh-intake__measurement-status">وضعیت سنجش
                    <select
                      value={measurementStatuses[item.id] ?? "SCORED"}
                      onChange={(event) => setMeasurementStatuses((current) => ({ ...current, [item.id]: event.target.value as MeasurementStatus }))}
                    >
                      <option value="SCORED">قابل امتیازدهی</option>
                      <option value="NOT_ASSESSED">سنجش‌نشده</option>
                      <option value="INSUFFICIENT_EVIDENCE">مدرک ناکافی</option>
                      <option value="CONFLICTING">دادهٔ متعارض</option>
                      <option value="NOT_APPLICABLE">نامربوط</option>
                    </select>
                  </label>
                  {(measurementStatuses[item.id] ?? "SCORED") !== "SCORED" ? (
                    <label className="fh-intake__measurement-note">دلیل ثبت وضعیت
                      <textarea
                        rows={2}
                        value={measurementNotes[item.id] ?? ""}
                        onChange={(event) => setMeasurementNotes((current) => ({ ...current, [item.id]: event.target.value }))}
                        placeholder="مثلاً مدرک هنوز دریافت نشده یا دو منبع با هم تعارض دارند"
                        required
                      />
                    </label>
                  ) : null}
                  <label className="fh-intake__score-row">
                    <span>مقدار ثبت‌شده</span>
                    <span className="fh-intake__number-wrap">
                      <input
                        aria-label={`مقدار ${item.category}`}
                        type="number"
                        min="0"
                        max="100"
                        step="1"
                        inputMode="numeric"
                        placeholder="۰ تا ۱۰۰"
                        disabled={(measurementStatuses[item.id] ?? "SCORED") !== "SCORED"}
                        required={(measurementStatuses[item.id] ?? "SCORED") === "SCORED"}
                        value={values[item.id] ?? ""}
                        onChange={(event) => setValues((current) => ({ ...current, [item.id]: event.target.value }))}
                      />
                      <small>از ۱۰۰</small>
                    </span>
                  </label>
                </fieldset>
              ))}
              {activeIndicators.length === 0 ? (
                <div className="fh-intake__empty">برای این دسته شاخص فعالی تعریف نشده است.</div>
              ) : null}
            </div>

            <div className="fh-intake__source-row">
              <label>
                پروندهٔ نمونه
                <select value={householdRef} onChange={(event) => setHouseholdRef(event.target.value)}>
                  {demoHouseholds.map((code) => <option key={code} value={code}>{code}</option>)}
                </select>
              </label>
              <label>
                منبع دادهٔ عددهای امتیازدار
                <select value={source} onChange={(event) => setSource(event.target.value)}>
                  <option value="">منبع را انتخاب کنید</option>
                  <option value="پرسشنامه استاندارد">پرسشنامه استاندارد</option>
                  <option value="ارزیابی کارشناسی">ارزیابی کارشناسی</option>
                  <option value="داده‌های محیطی">داده‌های محیطی</option>
                </select>
              </label>
              <label>
                تاریخ سنجش/اثر
                <input required type="date" value={effectiveAt} onChange={(event) => setEffectiveAt(event.target.value)} />
              </label>
            </div>
            <button className="fh-intake__submit" type="submit">ثبت مقادیر نمونه برای بازبینی <span aria-hidden="true">←</span></button>
          </form>
          {notice ? <p className="fh-intake__notice-text" role="status">{notice}</p> : null}
        </section>

        <aside className="fh-intake__card fh-intake__review">
          <div className="fh-intake__section-head">
            <div><small>روند ثبت</small><h2>ثبت و بازبینی انسانی</h2></div>
            <span className="fh-intake__review-icon" aria-hidden="true">✓</span>
          </div>
          <ol>
            <li><span>۱</span><div><strong>انتخاب دستهٔ PGOR</strong><small>مشاهدهٔ شاخص‌های فعال آن دسته</small></div></li>
            <li><span>۲</span><div><strong>ثبت مقدار، منبع و تاریخ</strong><small>هر مقدار با منشأ مستقل</small></div></li>
            <li><span>۳</span><div><strong>مرور و تصمیم انسانی</strong><small>تعارض‌ها حفظ و بررسی می‌شوند</small></div></li>
          </ol>
          <p>قرارداد فعلی سرور برای مشاهدهٔ PGOR عدد ۰ تا ۱۰۰ می‌گیرد. این دمو مقادیر را به سرور نمی‌فرستد و امتیاز رسمی تولید نمی‌کند.</p>
        </aside>
      </div>

      <section className="fh-intake__card fh-intake__history">
        <div className="fh-intake__section-head">
          <div><small>رد ثبت‌های نمایشی</small><h2>سوابق ثبت‌های دمو</h2></div>
          <span className="fh-intake__count">{entries.length.toLocaleString("fa-IR")} مقدار</span>
        </div>
        {entries.length === 0 ? (
          <div className="fh-intake__empty">ثبت‌های این پرونده پس از ارسال نمونه در این بخش می‌مانند.</div>
        ) : (
          <div className="fh-intake__entries">
            {entries.map((entry) => (
              <article className={entry.status === "RETURNED" ? "has-correction" : ""} key={entry.id}>
                <div><strong>{entry.group} · {entry.indicator} (نسخه {entry.indicatorRevision}): {entry.score === null ? "امتیاز ثبت نشده" : entry.score.toLocaleString("fa-IR")}</strong><small>وضعیت سنجش: {measurementStatusLabels[entry.measurementStatus]} · منبع: {entry.source ?? "ثبت نشده"} · تاریخ اثر: {entry.effectiveAt}</small>
                  {entry.measurementNote ? <small>توضیح وضعیت سنجش: {entry.measurementNote}</small> : null}
                  {entry.status === "RETURNED" ? <small>یادداشت بازبین: {entry.note}</small> : null}
                </div>
                <span className={`fh-review__status fh-review__status--${entry.status.toLowerCase()}`}>{entryStatusLabels[entry.status]}</span>
                {entry.status === "RETURNED" ? (
                  <form className="fh-intake__correction" onSubmit={(event) => resubmit(event, entry)}>
                    <label>مقدار اصلاح‌شده
                      <input name="score" type="number" min="0" max="100" step="1" defaultValue={entry.score ?? ""} required />
                    </label>
                    <label>منبع داده
                      <select name="source" defaultValue={entry.source ?? ""} required>
                        <option value="پرسشنامه استاندارد">پرسشنامه استاندارد</option>
                        <option value="ارزیابی کارشناسی">ارزیابی کارشناسی</option>
                        <option value="داده‌های محیطی">داده‌های محیطی</option>
                      </select>
                    </label>
                    <label>تاریخ سنجش/اثر
                      <input name="effectiveAt" type="date" defaultValue={entry.effectiveAt} required />
                    </label>
                    <button type="submit">ارسال نسخهٔ اصلاح‌شده برای بازبینی</button>
                  </form>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
