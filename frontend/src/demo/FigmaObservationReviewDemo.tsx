import { useEffect, useMemo, useState } from "react";
import { groups, type Group } from "./questionBank";

type ReviewStatus = "PENDING" | "ACCEPTED" | "RETURNED";
type ReviewRecord = {
  id: string;
  householdRef: string;
  group: Group;
  indicator: string;
  score: number;
  source: string;
  effectiveAt: string;
  submittedAt: string;
  status: ReviewStatus;
  note: string;
};

const storageKey = "hamoon-demo-observation-review-v1";
const initialRecords: ReviewRecord[] = [
  { id: "rev-01", householdRef: "HM-نمونه-۰۱", group: "P", indicator: "پیگیری امور", score: 68, source: "ارزیابی کارشناسی", effectiveAt: "2026-10-22", submittedAt: "2026-10-25", status: "PENDING", note: "مستند سنجش به ثبت پیوست نشده است." },
  { id: "rev-02", householdRef: "HM-نمونه-۰۲", group: "G", indicator: "مهارت", score: 54, source: "پرسشنامه استاندارد", effectiveAt: "2026-10-21", submittedAt: "2026-10-24", status: "PENDING", note: "برای بازبینی منبع ابزار سنجش مشخص شود." },
  { id: "rev-03", householdRef: "HM-نمونه-۰۳", group: "O", indicator: "فرصت اشتغال", score: 72, source: "داده‌های محیطی", effectiveAt: "2026-10-20", submittedAt: "2026-10-23", status: "ACCEPTED", note: "منبع داده بررسی شد." },
  { id: "rev-04", householdRef: "HM-نمونه-۰۴", group: "R", indicator: "ثبات درآمد", score: 41, source: "ارزیابی کارشناسی", effectiveAt: "2026-10-19", submittedAt: "2026-10-22", status: "RETURNED", note: "تاریخ اثر و دورهٔ سنجش تکمیل شود." },
  { id: "rev-05", householdRef: "HM-نمونه-۰۵", group: "P", indicator: "حضور در آموزش", score: 83, source: "پرسشنامه استاندارد", effectiveAt: "2026-10-22", submittedAt: "2026-10-24", status: "PENDING", note: "نیازمند تطبیق با شواهد حضور است." },
  { id: "rev-06", householdRef: "HM-نمونه-۰۶", group: "G", indicator: "سابقه کاری", score: 61, source: "ارزیابی کارشناسی", effectiveAt: "2026-10-18", submittedAt: "2026-10-21", status: "ACCEPTED", note: "برای نمونه پذیرفته شد." },
];

const statusLabels: Record<ReviewStatus, string> = {
  PENDING: "در انتظار بازبینی",
  ACCEPTED: "تأییدشده",
  RETURNED: "نیازمند اصلاح",
};

function loadRecords(): ReviewRecord[] {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (raw) {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed as ReviewRecord[];
    }
  } catch {
    // Use fictional sample records when browser storage is unavailable.
  }
  return initialRecords;
}

export function FigmaObservationReviewDemo() {
  const [records, setRecords] = useState<ReviewRecord[]>(loadRecords);
  const [status, setStatus] = useState<ReviewStatus | "ALL">("PENDING");
  const [group, setGroup] = useState<Group | "ALL">("ALL");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(records));
    } catch {
      // The review screen remains usable in memory.
    }
  }, [records]);

  const visible = useMemo(() => records.filter((record) =>
    (status === "ALL" || record.status === status) &&
    (group === "ALL" || record.group === group),
  ), [group, records, status]);

  function updateStatus(record: ReviewRecord, next: ReviewStatus) {
    setRecords((current) => current.map((item) =>
      item.id === record.id
        ? { ...item, status: next, note: next === "ACCEPTED" ? "بازبین داده را تأیید کرد." : "برای تکمیل یا اصلاح به مددکار بازگردانده شد." }
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
      </section>

      <div className="fh-review__filters">
        <label>وضعیت
          <select value={status} onChange={(event) => setStatus(event.target.value as ReviewStatus | "ALL")}>
            <option value="PENDING">در انتظار بازبینی</option>
            <option value="ACCEPTED">تأییدشده</option>
            <option value="RETURNED">نیازمند اصلاح</option>
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
              <div><span>{record.group} · {groups.find((item) => item.id === record.group)?.name}</span><strong>{record.indicator}</strong></div>
              <b className={`fh-review__status fh-review__status--${record.status.toLowerCase()}`}>{statusLabels[record.status]}</b>
            </div>
            <div className="fh-review__facts">
              <div><small>شناسهٔ ساختگی خانوار</small><strong>{record.householdRef}</strong></div>
              <div><small>مقدار ثبت‌شده</small><strong>{record.score.toLocaleString("fa-IR")} از ۱۰۰</strong></div>
              <div><small>منبع داده</small><strong>{record.source}</strong></div>
              <div><small>تاریخ اثر</small><strong>{record.effectiveAt}</strong></div>
              <div><small>تاریخ ثبت</small><strong>{record.submittedAt}</strong></div>
            </div>
            <p className="fh-review__note">{record.note}</p>
            {record.status === "PENDING" ? (
              <div className="fh-review__actions">
                <button onClick={() => updateStatus(record, "ACCEPTED")} type="button">تأیید ثبت</button>
                <button onClick={() => updateStatus(record, "RETURNED")} type="button">بازگشت برای اصلاح</button>
              </div>
            ) : null}
          </article>
        ))}
        {visible.length === 0 ? <div className="fh-question-admin__empty">در این فیلتر موردی ثبت نشده است.</div> : null}
      </section>
      <footer className="fh-question-admin__footer">وضعیت‌های این دمو در حافظهٔ مرورگر ذخیره می‌شوند؛ ثبت و تأیید واقعی به API، کاربر بازبین و ثبت تاریخچهٔ تغییرات نیاز دارد.</footer>
    </main>
  );
}
