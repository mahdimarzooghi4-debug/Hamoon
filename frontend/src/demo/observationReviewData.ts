import type { Group } from "./questionBank";

export type ReviewStatus = "PENDING" | "ACCEPTED" | "RETURNED" | "SUPERSEDED";
export type MeasurementStatus = "SCORED" | "NOT_ASSESSED" | "INSUFFICIENT_EVIDENCE" | "CONFLICTING" | "NOT_APPLICABLE";
export type ReviewRecord = {
  id: string;
  householdRef: string;
  group: Group;
  indicatorId: string;
  indicatorRevision: number;
  indicator: string;
  indicatorGuidance: string;
  score: number | null;
  measurementStatus: MeasurementStatus;
  measurementNote: string;
  source: string | null;
  effectiveAt: string;
  submittedAt: string;
  status: ReviewStatus;
  note: string;
  supersedesId?: string;
};

const storageKey = "hamoon-demo-observation-review-v1";
const initialRecords: ReviewRecord[] = [
  { id: "rev-01", indicatorId: "p-followup", indicatorRevision: 1, measurementStatus: "SCORED", measurementNote: "", indicatorGuidance: "پیگیری امور و اقدام‌های مورد توافق را بر اساس سوابق ثبت کنید.", householdRef: "HM-نمونه-۰۱", group: "P", indicator: "پیگیری امور", score: 68, source: "ارزیابی کارشناسی", effectiveAt: "2026-10-22", submittedAt: "2026-10-25", status: "PENDING", note: "مستند سنجش به ثبت پیوست نشده است." },
  { id: "rev-02", indicatorId: "g-skills", indicatorRevision: 1, measurementStatus: "SCORED", measurementNote: "", indicatorGuidance: "مهارت‌های قابل استفاده اعضای خانوار را بر اساس شواهد ثبت کنید.", householdRef: "HM-نمونه-۰۲", group: "G", indicator: "مهارت", score: 54, source: "پرسشنامه استاندارد", effectiveAt: "2026-10-21", submittedAt: "2026-10-24", status: "PENDING", note: "برای بازبینی منبع ابزار سنجش مشخص شود." },
  { id: "rev-03", indicatorId: "o-jobs", indicatorRevision: 1, measurementStatus: "SCORED", measurementNote: "", indicatorGuidance: "فرصت‌های اشتغال قابل دسترس را بر اساس داده‌های موجود ثبت کنید.", householdRef: "HM-نمونه-۰۳", group: "O", indicator: "فرصت اشتغال", score: 72, source: "داده‌های محیطی", effectiveAt: "2026-10-20", submittedAt: "2026-10-23", status: "ACCEPTED", note: "منبع داده بررسی شد." },
  { id: "rev-04", indicatorId: "r-income", indicatorRevision: 1, measurementStatus: "SCORED", measurementNote: "", indicatorGuidance: "ثبات و قابلیت پیش‌بینی منابع درآمدی را از داده‌های در دسترس ارزیابی کنید.", householdRef: "HM-نمونه-۰۴", group: "R", indicator: "ثبات درآمد", score: 41, source: "ارزیابی کارشناسی", effectiveAt: "2026-10-19", submittedAt: "2026-10-22", status: "RETURNED", note: "تاریخ اثر و دورهٔ سنجش تکمیل شود." },
  { id: "rev-05", indicatorId: "p-training", indicatorRevision: 1, measurementStatus: "SCORED", measurementNote: "", indicatorGuidance: "حضور در دوره‌ها و فعالیت‌های آموزشی ثبت‌شده را ارزیابی کنید.", householdRef: "HM-نمونه-۰۵", group: "P", indicator: "حضور در آموزش", score: 83, source: "پرسشنامه استاندارد", effectiveAt: "2026-10-22", submittedAt: "2026-10-24", status: "PENDING", note: "نیازمند تطبیق با شواهد حضور است." },
  { id: "rev-06", indicatorId: "g-work", indicatorRevision: 1, measurementStatus: "SCORED", measurementNote: "", indicatorGuidance: "سابقه کاری ثبت‌شده اعضای خانوار را ارزیابی کنید.", householdRef: "HM-نمونه-۰۶", group: "G", indicator: "سابقه کاری", score: 61, source: "ارزیابی کارشناسی", effectiveAt: "2026-10-18", submittedAt: "2026-10-21", status: "ACCEPTED", note: "برای نمونه پذیرفته شد." },
];

const measurementStatuses: MeasurementStatus[] = ["SCORED", "NOT_ASSESSED", "INSUFFICIENT_EVIDENCE", "CONFLICTING", "NOT_APPLICABLE"];

function isMeasurementStatus(value: unknown): value is MeasurementStatus {
  return typeof value === "string" && measurementStatuses.includes(value as MeasurementStatus);
}

const legacySnapshots: Record<string, Pick<ReviewRecord, "indicatorId" | "indicatorRevision" | "indicatorGuidance">> = {
  "rev-01": { indicatorId: "p-followup", indicatorRevision: 1, indicatorGuidance: "پیگیری امور و اقدام‌های مورد توافق را بر اساس سوابق ثبت کنید." },
  "rev-02": { indicatorId: "g-skills", indicatorRevision: 1, indicatorGuidance: "مهارت‌های قابل استفاده اعضای خانوار را بر اساس شواهد ثبت کنید." },
  "rev-03": { indicatorId: "o-jobs", indicatorRevision: 1, indicatorGuidance: "فرصت‌های اشتغال قابل دسترس را بر اساس داده‌های موجود ثبت کنید." },
  "rev-04": { indicatorId: "r-income", indicatorRevision: 1, indicatorGuidance: "ثبات و قابلیت پیش‌بینی منابع درآمدی را از داده‌های در دسترس ارزیابی کنید." },
  "rev-05": { indicatorId: "p-training", indicatorRevision: 1, indicatorGuidance: "حضور در دوره‌ها و فعالیت‌های آموزشی ثبت‌شده را ارزیابی کنید." },
  "rev-06": { indicatorId: "g-work", indicatorRevision: 1, indicatorGuidance: "سابقه کاری ثبت‌شده اعضای خانوار را ارزیابی کنید." },
};

export function loadDemoReviewRecords(): ReviewRecord[] {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (raw) {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed
        .filter((value): value is Record<string, unknown> => typeof value === "object" && value !== null)
        .map((value, index) => {
          const legacy = legacySnapshots[String(value.id ?? "")];
          return {
            ...value,
            score: typeof value.score === "number" && Number.isFinite(value.score) ? value.score : null,
            source: typeof value.source === "string" ? value.source : null,
            measurementStatus: isMeasurementStatus(value.measurementStatus)
              ? value.measurementStatus
              : typeof value.score === "number" ? "SCORED" : "NOT_ASSESSED",
            measurementNote: typeof value.measurementNote === "string" ? value.measurementNote : "",
            indicatorId: typeof value.indicatorId === "string" && !value.indicatorId.startsWith("legacy-")
              ? value.indicatorId
              : legacy?.indicatorId ?? "legacy-" + String(value.id ?? index),
            indicatorRevision: Number.isInteger(value.indicatorRevision) && Number(value.indicatorRevision) > 0
              ? Number(value.indicatorRevision)
              : legacy?.indicatorRevision ?? 1,
            indicatorGuidance: typeof value.indicatorGuidance === "string"
              && value.indicatorGuidance !== "راهنمای نسخهٔ قبلی در این ثبت موجود نیست."
              ? value.indicatorGuidance
              : legacy?.indicatorGuidance ?? "راهنمای نسخهٔ قبلی در این ثبت موجود نیست.",
          };
        }) as ReviewRecord[];
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
