import { useEffect, useMemo, useState } from "react";
import { groups, type Group } from "./questionBank";
import type { MeasurementStatus } from "./observationReviewData";
import { loadDemoReviewRecords, saveDemoReviewRecords, type ReviewRecord, type ReviewStatus } from "./observationReviewData";

const statusLabels: Record<ReviewStatus, string> = {
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

export function FigmaObservationReviewDemo() {
  const [records, setRecords] = useState<ReviewRecord[]>(loadDemoReviewRecords);
  const [status, setStatus] = useState<ReviewStatus | "ALL">("PENDING");
  const [group, setGroup] = useState<Group | "ALL">("ALL");
  const [notice, setNotice] = useState("");
  const [returnNotes, setReturnNotes] = useState<Record<string, string>>({});

  useEffect(() => {
    saveDemoReviewRecords(records);
  }, [records]);

  const visible = useMemo(() => records.filter((record) =>
    (status === "ALL" || record.status === status) &&
    (group === "ALL" || record.group === group),
  ), [group, records, status]);

  function updateStatus(record: ReviewRecord, next: ReviewStatus, returnNote = "") {
    setRecords((current) => current.map((item) =>
      item.id === record.id
        ? { ...item, status: next, note: next === "ACCEPTED" ? "بازبین داده را تأیید کرد." : returnNote.trim() }
        : item,
    ));
    setNotice(next === "ACCEPTED"
      ? "ثبت به‌عنوان دادهٔ بازبینی‌شده علامت‌گذاری شد."
      : "ثبت برای اصلاح به مددکار بازگردانده شد.");
  }

  const pendingCount = records.filter((record) => record.status === "PENDING").length;

  return (
    <main className="fh-review" dir="rtl" aria-label="بازبینی داده‌های PGOR">
      <header className="fh-review__header">
        <div>
          <span className="fh-intake__eyebrow">پنل بازبینی · نسخهٔ نمایشی</span>
          <h1>بازبینی ثبت‌های PGOR</h1>
          <p>سرپرست، عدد و مشخصات منبع را مرور می‌کند و ثبت را تأیید یا برای اصلاح برمی‌گرداند.</p>
        </div>
        <span className="fh-intake__badge">{pendingCount.toLocaleString("fa-IR")} مورد در انتظار</span>
      </header>

      <div className="fh-review__notice" role="note">
        همهٔ پرونده‌ها و اعداد این صفحه ساختگی‌اند. تأیید در دمو فقط وضعیت را عوض می‌کند و به دیتاست واقعی یا آموزش مدل اضافه نمی‌شود.
      </div>

      <section className="fh-review__summary">
        <article><small>در انتظار بازبینی</small><strong>{pendingCount.toLocaleString("fa-IR")}</strong></article>
        <article><small>تأییدشده</small><strong>{records.filter((item) => item.status === "ACCEPTED").length.toLocaleString("fa-IR")}</strong></article>
        <article><small>نیازمند اصلاح</small><strong>{records.filter((item) => item.status === "RETURNED").length.toLocaleString("fa-IR")}</strong></article>
        <article><small>جایگزین‌شده</small><strong>{records.filter((item) => item.status === "SUPERSEDED").length.toLocaleString("fa-IR")}</strong></article>
      </section>

      <div className="fh-review__filters">
        <label>وضعیت
          <select value={status} onChange={(event) => setStatus(event.target.value as ReviewStatus | "ALL")}>
            <option value="PENDING">در انتظار بازبینی</option>
            <option value="ACCEPTED">تأییدشده</option>
            <option value="RETURNED">نیازمند اصلاح</option>
            <option value="SUPERSEDED">جایگزین‌شده</option>
            <option value="ALL">همه</option>
          </select>
        </label>
        <label>دستهٔ PGOR
          <select value={group} onChange={(event) => setGroup(event.target.value as Group | "ALL")}>
            <option value="ALL">همهٔ دسته‌ها</option>
            {groups.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}
          </select>
        </label>
      </div>

      {notice ? <p className="fh-review__toast" role="status">{notice}</p> : null}

      <section className="fh-review__list" aria-label="ثبت‌های قابل بازبینی">
        {visible.map((record) => (
          <article className="fh-review__card" key={record.id}>
            <div className="fh-review__card-head">
              <div><span>{record.group} · {groups.find((item) => item.id === record.group)?.name}</span><strong>{record.indicator}</strong><small>نسخهٔ شاخص {record.indicatorRevision} · {record.indicatorId}</small></div>
              <b className={`fh-review__status fh-review__status--${record.status.toLowerCase()}`}>{statusLabels[record.status]}</b>
            </div>
            <div className="fh-review__facts">
              <div><small>شناسهٔ ساختگی خانوار</small><strong>{record.householdRef}</strong></div>
              <div><small>مقدار ثبت‌شده</small><strong>{record.score === null ? "امتیاز ثبت نشده" : `${record.score.toLocaleString("fa-IR")} از ۱۰۰`}</strong></div>
              <div><small>وضعیت سنجش</small><strong>{measurementStatusLabels[record.measurementStatus]}</strong></div>
              <div><small>منبع داده</small><strong>{record.source ?? "ثبت نشده"}</strong></div>
              <div><small>تاریخ اثر</small><strong>{record.effectiveAt}</strong></div>
              <div><small>بازهٔ سنجش</small><strong>{record.periodStart && record.periodEnd ? `${record.periodStart} تا ${record.periodEnd}` : "بازه ثبت نشده"}</strong></div>
              <div><small>تاریخ ثبت</small><strong>{record.submittedAt}</strong></div>
            </div>
            <p className="fh-review__guidance">راهنمای ثبت در زمان ثبت: {record.indicatorGuidance}</p>
            {record.measurementNote ? <p className="fh-review__note">توضیح وضعیت سنجش: {record.measurementNote}</p> : null}
            <p className="fh-review__note">{record.note}</p>
            {record.supersedesId ? (
              <p className="fh-review__supersedes">پاسخ به ثبت برگشتی: {record.supersedesId} · ثبت قبلی در تاریخچه حفظ شده است.</p>
            ) : null}
            {record.status === "PENDING" ? (
              <>
              <label className="fh-review__return-note">یادداشت اصلاح برای مددکار
                <textarea
                  rows={2}
                  value={returnNotes[record.id] ?? ""}
                  onChange={(event) => setReturnNotes((current) => ({ ...current, [record.id]: event.target.value }))}
                  placeholder="دقیقاً بنویسید چه چیزی باید تکمیل یا اصلاح شود"
                />
              </label>
              <div className="fh-review__actions">
                <button onClick={() => updateStatus(record, "ACCEPTED")} type="button">تأیید ثبت</button>
                <button
                  disabled={!returnNotes[record.id]?.trim()}
                  onClick={() => updateStatus(record, "RETURNED", returnNotes[record.id] ?? "")}
                  type="button"
                >بازگشت برای اصلاح</button>
              </div>
              </>
            ) : null}
          </article>
        ))}
        {visible.length === 0 ? <div className="fh-question-admin__empty">در این فیلتر موردی ثبت نشده است.</div> : null}
      </section>
      <footer className="fh-question-admin__footer">وضعیت‌های این دمو در حافظهٔ مرورگر ذخیره می‌شوند؛ ثبت و تأیید واقعی به API، کاربر بازبین و ثبت تاریخچهٔ تغییرات نیاز دارد.</footer>
    </main>
  );
}
