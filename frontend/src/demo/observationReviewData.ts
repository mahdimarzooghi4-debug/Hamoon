import type { Group } from "./questionBank";

export type ReviewStatus = "PENDING" | "ACCEPTED" | "RETURNED";
export type ReviewRecord = {
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

export function loadDemoReviewRecords(): ReviewRecord[] {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (raw) {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed as ReviewRecord[];
    }
  } catch {
    // Use fictional records while browser storage is unavailable.
  }
  return initialRecords;
}

export function saveDemoReviewRecords(records: ReviewRecord[]): void {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(records));
  } catch {
    // Keep the current demo state in memory.
  }
}

export function addDemoReviewRecords(records: ReviewRecord[]): void {
  if (records.length === 0) return;
  saveDemoReviewRecords([...records, ...loadDemoReviewRecords()]);
}
