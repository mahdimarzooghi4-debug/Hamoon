import { useEffect, useMemo, useState } from "react";
import {
  loadDemoIndicators,
  saveDemoIndicators,
  type DemoIndicator,
  type DemoIndicatorSnapshot,
} from "./questionBank";

function snapshotIndicator(item: DemoIndicator): DemoIndicatorSnapshot {
  return {
    revision: item.revision,
    category: item.category,
    guidance: item.guidance,
    measurementMethod: item.measurementMethod,
    score0Anchor: item.score0Anchor,
    score50Anchor: item.score50Anchor,
    score100Anchor: item.score100Anchor,
    analysisUnitRule: item.analysisUnitRule,
    evidenceSources: [...item.evidenceSources],
    evidencePeriodGuidance: item.evidencePeriodGuidance,
    householdAggregationGuidance: item.householdAggregationGuidance,
  };
}

export function FigmaIndicatorApprovalDemo() {
  const [indicators, setIndicators] = useState<DemoIndicator[]>(loadDemoIndicators);
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");

  useEffect(() => saveDemoIndicators(indicators), [indicators]);

  const pending = useMemo(
    () => indicators.filter((item) => item.approvalStatus === "IN_REVIEW"),
    [indicators],
  );

  function decide(indicator: DemoIndicator, status: "APPROVED" | "CHANGES_REQUESTED") {
    const note = (reviewNotes[indicator.id] ?? "").trim();
    if (status === "CHANGES_REQUESTED" && !note) return;
    const event = {
      status,
      revision: indicator.revision,
      note: status === "CHANGES_REQUESTED" ? note : "",
      at: new Date().toISOString(),
    };
    setIndicators((current) => current.map((item) => item.id !== indicator.id ? item : ({
      ...item,
      approvalStatus: status,
      draft: status !== "APPROVED",
      approvedRevision: status === "APPROVED" ? item.revision : item.approvedRevision,
      approvedSnapshot: status === "APPROVED" ? snapshotIndicator(item) : item.approvedSnapshot,
      reviewNote: status === "CHANGES_REQUESTED" ? note : "",
      approvalHistory: [...item.approvalHistory, event],
    })));
    setReviewNotes((current) => ({ ...current, [indicator.id]: "" }));
    setNotice(status === "APPROVED"
      ? `نسخهٔ ${indicator.revision} تأیید شد و snapshot آن برای فرم مددکار ثبت شد.`
      : `نسخهٔ ${indicator.revision} برای اصلاح برگشت خورد؛ بازبین یادداشت را ثبت کرد.`);
  }

  return (
    <main className="fh-question-admin" dir="rtl" aria-label="بازبینی تخصصی شاخص‌ها">
      <header className="fh-question-admin__header">
        <div>
          <span className="fh-intake__eyebrow">پنل بازبین تخصصی · نسخهٔ نمایشی</span>
          <h1>بازبینی نسخه‌های شاخص</h1>
          <p>بازبین فقط نسخه‌های ارسالی را می‌بیند؛ تأیید، snapshot همین نسخه را برای فرم ثبت مددکار آماده می‌کند.</p>
        </div>
      </header>

      <div className="fh-question-admin__notice" role="note">
        این صفحه نقش بازبین را فقط برای نمایش شبیه‌سازی می‌کند. ورود، تفکیک دسترسی و ثبت سروری وجود ندارد؛ همهٔ تصمیم‌ها در حافظهٔ همین مرورگر می‌مانند. نسخهٔ تأییدشده به معنی تصویب علمی محتوا نیست مگر متخصص واقعی آن را بررسی کند.
      </div>

      {notice ? <p className="fh-question-admin__toast" role="status">{notice}</p> : null}

      <section className="fh-question-admin__list" aria-label="نسخه‌های در انتظار بازبینی">
        {pending.map((indicator, index) => (
          <article className="fh-question-admin__item" key={indicator.id}>
            <div className="fh-question-admin__index">{String(index + 1).padStart(2, "0")}</div>
            <div className="fh-question-admin__copy">
              <div className="fh-question-admin__meta">
                <span>{indicator.group} · {indicator.groupName} · نسخهٔ {indicator.revision}</span>
                <b>{indicator.category}</b>
              </div>
              <p>{indicator.guidance}</p>
              <small>روش سنجش: {indicator.measurementMethod || "تعریف نشده"} · لنگرهای ۰ / ۵۰ / ۱۰۰: {indicator.score0Anchor || "تعریف نشده"} · {indicator.score50Anchor || "تعریف نشده"} · {indicator.score100Anchor || "تعریف نشده"}</small>
              <small>سطح تحلیل: {indicator.analysisUnitRule === "UNRESOLVED" ? "تعریف نشده" : indicator.analysisUnitRule === "MEMBER" ? "عضو" : indicator.analysisUnitRule === "HOUSEHOLD" ? "خانوار" : "منطقه"} · منابع: {indicator.evidenceSources.length ? indicator.evidenceSources.join("، ") : "تعریف نشده"}</small>
              <small>تازگی شواهد: {indicator.evidencePeriodGuidance || "تعریف نشده"} · تجمیع عضو به خانوار: {indicator.householdAggregationGuidance || "تعریف نشده"}</small>
              {indicator.approvedRevision ? <small>نسخهٔ مصوب قبلی: {indicator.approvedRevision}؛ این تصمیم فقط دربارهٔ نسخهٔ {indicator.revision} است.</small> : null}
              <details className="fh-question-admin__history">
                <summary>تاریخچهٔ بازبینی ({indicator.approvalHistory.length})</summary>
                {indicator.approvalHistory.length ? <ul>{indicator.approvalHistory.slice().reverse().map((event, eventIndex) => (
                  <li key={`${event.revision}-${event.status}-${event.at}-${eventIndex}`}>
                    نسخهٔ {event.revision} · {event.status === "IN_REVIEW" ? "ارسال برای بازبینی" : event.status === "APPROVED" ? "تأیید تخصصی" : event.status === "CHANGES_REQUESTED" ? "برگشت برای اصلاح" : "پیش‌نویس"} · {new Date(event.at).toLocaleString("fa-IR")}
                    {event.note ? ` · ${event.note}` : ""}
                  </li>
                ))}</ul> : <small>تاریخچه‌ای ثبت نشده است.</small>}
              </details>
            </div>
            <div className="fh-question-admin__actions">
              <button onClick={() => decide(indicator, "APPROVED")} type="button">تأیید نسخهٔ ارسالی</button>
              <label className="fh-question-admin__review-note">دلیل برگشت برای اصلاح
                <textarea rows={3} value={reviewNotes[indicator.id] ?? ""} onChange={(event) => setReviewNotes((current) => ({ ...current, [indicator.id]: event.target.value }))} placeholder="برای بازگشت، دلیل روشن بنویسید" />
              </label>
              <button disabled={!(reviewNotes[indicator.id] ?? "").trim()} onClick={() => decide(indicator, "CHANGES_REQUESTED")} type="button">برگشت برای اصلاح</button>
            </div>
          </article>
        ))}
        {pending.length === 0 ? <p className="fh-question-admin__empty">نسخه‌ای در انتظار بازبینی نیست. مدیر ابتدا باید پیش‌نویس را ارسال کند.</p> : null}
      </section>

      <footer className="fh-question-admin__footer">این نسخهٔ نمایشی برای تصمیم واقعی، آموزش مدل یا تأیید تخصصی استفاده نمی‌شود.</footer>
    </main>
  );
}
