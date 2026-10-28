import { useState, type FormEvent } from "react";
import { groups, loadDemoIndicators, type Group } from "./questionBank";
import { addDemoReviewRecords, loadDemoReviewRecords, type ReviewStatus } from "./observationReviewData";

type DemoEntry = {
  id: string;
  group: Group;
  indicatorId: string;
  indicatorRevision: number;
  indicator: string;
  indicatorGuidance: string;
  score: number;
  source: string;
  effectiveAt: string;
  note: string;
  status: ReviewStatus;
};

const entryStatusLabels: Record<ReviewStatus, string> = {
  PENDING: "در انتظار بازبینی",
  ACCEPTED: "تأییدشده",
  RETURNED: "نیازمند اصلاح",
};

const summaries: Record<Group, string> = {
  P: "شاخص‌های مشارکت خانوار در فرایند تغییر",
  G: "شاخص‌های ظرفیت رشد خانوار",
  O: "شاخص‌های فرصت و دسترسی",
  R: "شاخص‌های تاب‌آوری خانوار",
};

export function FigmaIntakeDemo() {
  const [dimension, setDimension] = useState<Group>("P");
  const [values, setValues] = useState<Record<string, string>>({});
  const [source, setSource] = useState("");
  const [effectiveAt, setEffectiveAt] = useState("");
  const [entries, setEntries] = useState<DemoEntry[]>(() => loadDemoReviewRecords()
    .filter((record) => record.id.startsWith("field-"))
    .map((record) => ({
      id: record.id,
      group: record.group,
      indicatorId: record.indicatorId,
      indicatorRevision: record.indicatorRevision,
      indicator: record.indicator,
      indicatorGuidance: record.indicatorGuidance,
      score: record.score,
      source: record.source,
      effectiveAt: record.effectiveAt,
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
    if (!source || !effectiveAt) {
      setNotice("منبع داده و تاریخ اثر را تکمیل کنید.");
      return;
    }
    const entered = activeIndicators.filter((item) => values[item.id] !== undefined && values[item.id] !== "");
    const invalid = entered.some((item) => {
      const value = Number(values[item.id]);
      return !Number.isFinite(value) || value < 0 || value > 100;
    });
    if (invalid) {
      setNotice("عدد هر شاخص باید بین ۰ تا ۱۰۰ باشد.");
      return;
    }
    if (entered.length === 0) {
      setNotice("برای ثبت نمونه، عدد دست‌کم یک شاخص را وارد کنید.");
      return;
    }
    const completed = entered.map((item, index) => ({
      id: `field-${Date.now() + index}`,
      group: dimension,
      indicatorId: item.id,
      indicatorRevision: item.revision,
      indicator: item.category,
      indicatorGuidance: item.guidance,
      score: Number(values[item.id]),
      source,
      effectiveAt,
      note: "ثبت تازه از فرم مددکار؛ در انتظار بازبینی.",
      status: "PENDING" as const,
    }));
    const submittedAt = new Date().toISOString().slice(0, 10);
    addDemoReviewRecords(completed.map((entry) => ({
      id: entry.id,
      householdRef: "HM-نمونه-۲۱",
      group: entry.group,
      indicatorId: entry.indicatorId,
      indicatorRevision: entry.indicatorRevision,
      indicator: entry.indicator,
      indicatorGuidance: entry.indicatorGuidance,
      score: entry.score,
      source: entry.source,
      effectiveAt: entry.effectiveAt,
      submittedAt,
      status: "PENDING" as const,
      note: entry.note,
    })));
    setEntries((current) => [...completed.reverse(), ...current]);
    setValues({});
    setSource("");
    setEffectiveAt("");
    setNotice("مقادیر به صف بازبینی همین دمو اضافه شدند؛ به سرور ارسال نمی‌شوند.");
  }

  return (
    <main className="fh-intake" aria-label="دموی ثبت عددی شاخص‌های PGOR" dir="rtl">
      <header className="fh-intake__heading">
        <div>
          <span className="fh-intake__eyebrow">دموی محیط مددکار · پرونده HM-1405-021</span>
          <h1>ثبت میدانی داده‌های خانوار</h1>
          <p>مددکار مقدار عددی هر شاخص را همراه منبع و تاریخ ثبت می‌کند؛ این صفحه پرسش‌نامهٔ مصاحبه‌ای نیست.</p>
        </div>
        <span className="fh-intake__badge">نمونهٔ ساختگی</span>
      </header>

      <div className="fh-intake__notice" role="note">
        <strong>دموی بدون اتصال</strong>
        <span>اطلاعات واقعی وارد نکنید. بازهٔ عددی ۰ تا ۱۰۰ است، اما روش تعیین عدد باید جداگانه تأیید شود.</span>
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
                منبع داده
                <select required value={source} onChange={(event) => setSource(event.target.value)}>
                  <option value="">منبع را انتخاب کنید</option>
                  <option value="پرسشنامه استاندارد">پرسشنامه استاندارد</option>
                  <option value="ارزیابی کارشناسی">ارزیابی کارشناسی</option>
                  <option value="داده‌های محیطی">داده‌های محیطی</option>
                </select>
              </label>
              <label>
                تاریخ اثر
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
              <article key={entry.id}>
                <div><strong>{entry.group} · {entry.indicator} (نسخه {entry.indicatorRevision}): {entry.score.toLocaleString("fa-IR")}</strong><small>منبع: {entry.source} · تاریخ اثر: {entry.effectiveAt}</small>
                  {entry.status === "RETURNED" ? <small>یادداشت بازبین: {entry.note}</small> : null}
                </div>
                <span className={`fh-review__status fh-review__status--${entry.status.toLowerCase()}`}>{entryStatusLabels[entry.status]}</span>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
