import { useCallback, useEffect, useMemo, useState, type FormEvent, type ChangeEvent } from "react";

import { ApiError } from "../api/client";
import {
  finalizeEvidence,
  getEvidenceDownloadTarget,
  getHouseholdEvidence,
  initEvidenceUpload,
  uploadEvidenceContent,
  type EvidenceLifecycleStatus,
  type EvidenceRecord,
  type EvidenceSensitivity,
  type EvidenceType,
} from "../api/evidence";
import { getHousehold, type HouseholdSummary } from "../api/households";
import { AppLink } from "../app/navigation";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  Panel,
} from "../design-system/components";
import { hamoonRuntimeConfig } from "../runtimeConfig";

type HouseholdState =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "not-found" }
  | { kind: "error" }
  | { kind: "ready"; item: HouseholdSummary };

type EvidenceState =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "forbidden" }
  | { kind: "error" }
  | { kind: "ready"; items: EvidenceRecord[] };

type EvidenceFilter = "ALL" | "PROCESSING" | "AVAILABLE" | "BLOCKED";

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const allowedMediaTypes = new Set([
  "application/pdf",
  "image/jpeg",
  "image/png",
  "text/plain",
]);

const evidenceTypeLabels: Record<EvidenceType, string> = {
  DOCUMENT: "سند",
  IMAGE: "تصویر",
  PROVIDER_REPORT: "گزارش ارائه‌دهنده",
  ASSESSMENT_ATTACHMENT: "پیوست ارزیابی",
  OTHER: "سایر مدارک",
};

const sensitivityLabels: Record<EvidenceSensitivity, string> = {
  INTERNAL: "داخلی",
  CONFIDENTIAL: "محرمانه",
  SENSITIVE_PERSONAL: "اطلاعات شخصی حساس",
  HIGHLY_SENSITIVE: "بسیار حساس",
};

const lifecycleLabels: Record<EvidenceLifecycleStatus, string> = {
  PENDING_UPLOAD: "در انتظار بارگذاری",
  UPLOADED: "در انتظار بررسی",
  SCANNING: "در حال بررسی امنیتی",
  AVAILABLE: "در دسترس",
  UPLOAD_FAILED: "بارگذاری ناموفق",
  SCAN_FAILED: "بررسی ناموفق",
  QUARANTINED: "قرنطینه",
  REJECTED: "رد شده",
  ARCHIVED: "بایگانی‌شده",
};

const recordedAtFormatter = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function lifecycleTone(
  item: EvidenceRecord,
): "success" | "warning" | "neutral" | "danger" {
  if (isAvailable(item)) return "success";
  if (
    item.lifecycle_status === "QUARANTINED"
    || item.lifecycle_status === "SCAN_FAILED"
    || item.lifecycle_status === "REJECTED"
    || item.scan_status === "FAILED"
    || item.scan_status === "INFECTED"
    || (item.lifecycle_status === "AVAILABLE" && item.scan_status !== "CLEAN")
  ) {
    return "danger";
  }
  if (
    item.lifecycle_status === "PENDING_UPLOAD"
    || item.lifecycle_status === "UPLOADED"
    || item.lifecycle_status === "SCANNING"
  ) {
    return "warning";
  }
  return "neutral";
}

function isAvailable(item: EvidenceRecord): boolean {
  return item.lifecycle_status === "AVAILABLE" && item.scan_status === "CLEAN";
}

function isProcessing(item: EvidenceRecord): boolean {
  return (
    !isBlocked(item)
    && (
      item.lifecycle_status === "PENDING_UPLOAD"
      || item.lifecycle_status === "UPLOADED"
      || item.lifecycle_status === "SCANNING"
    )
  );
}

function isBlocked(item: EvidenceRecord): boolean {
  return (
    item.lifecycle_status === "QUARANTINED"
    || item.lifecycle_status === "SCAN_FAILED"
    || item.lifecycle_status === "REJECTED"
    || item.lifecycle_status === "UPLOAD_FAILED"
    || item.lifecycle_status === "ARCHIVED"
    || item.scan_status === "FAILED"
    || item.scan_status === "INFECTED"
    || (item.lifecycle_status === "AVAILABLE" && item.scan_status !== "CLEAN")
  );
}

function mediaTypeFor(file: File): string {
  const extension = file.name.split(".").pop()?.toLowerCase();
  const byExtension: Record<string, string> = {
    pdf: "application/pdf",
    png: "image/png",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    txt: "text/plain",
  };
  if (extension && byExtension[extension]) return byExtension[extension];
  return file.type;
}

async function sha256Hex(file: File): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new Error("SECURE_HASHING_UNAVAILABLE");
  }
  const content = await file.arrayBuffer();
  const digest = await globalThis.crypto.subtle.digest("SHA-256", content);
  return Array.from(
    new Uint8Array(digest),
    (byte) => byte.toString(16).padStart(2, "0"),
  ).join("");
}

function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes.toLocaleString("fa-IR")} بایت`;
  const megabytes = bytes / (1024 * 1024);
  return `${megabytes.toLocaleString("fa-IR", { maximumFractionDigits: 2 })} مگابایت`;
}

function actionErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message === "SECURE_HASHING_UNAVAILABLE") {
    return "برای ثبت امن اثر انگشت فایل، مرورگر باید در بستر امن HTTPS یا localhost اجرا شود.";
  }
  if (error instanceof ApiError) {
    if (error.code === "AUTH_REQUIRED") return "برای ادامه، ورود سازمانی معتبر لازم است.";
    if (error.code === "MEDIA_TYPE_REJECTED") return "قالب فایل با سیاست امنیتی سامانه مجاز نیست.";
    if (error.code === "EVIDENCE_SIZE_REJECTED" || error.status === 413) {
      return "حجم فایل از حد مجاز سامانه بیشتر است.";
    }
    if (error.code.includes("SCANNER") || error.code === "EVIDENCE_STORAGE_UNAVAILABLE") {
      return "سرویس امن ذخیره‌سازی یا اسکن فعلاً در دسترس نیست؛ مدرک تا بررسی موفق قابل دانلود نخواهد بود.";
    }
    if (error.status === 403 || error.status === 404) {
      return "مدرک یا مجوز دسترسی در دسترس نیست. سطح دسترسی سازمانی را بررسی کنید.";
    }
    if (error.status === 409) {
      return "نشست بارگذاری منقضی یا مصرف شده است. بارگذاری را از ابتدا آغاز کنید.";
    }
  }
  return "عملیات مدرک تکمیل نشد. وضعیت پرونده را تازه‌سازی کنید و از تکرار بارگذاری در حال اجرا خودداری کنید.";
}

export function HouseholdEvidencePage({ householdId }: { householdId: string }) {
  const [householdState, setHouseholdState] = useState<HouseholdState>({ kind: "loading" });
  const [evidenceState, setEvidenceState] = useState<EvidenceState>({ kind: "loading" });
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [evidenceType, setEvidenceType] = useState<EvidenceType | "">("");
  const [sensitivity, setSensitivity] = useState<EvidenceSensitivity | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [fileInputVersion, setFileInputVersion] = useState(0);
  const [filter, setFilter] = useState<EvidenceFilter>("ALL");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<"hashing" | "initiating" | "uploading" | "scanning" | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadEvidence = useCallback(async () => {
    setEvidenceState({ kind: "loading" });
    setDownloadError(null);
    try {
      setEvidenceState({ kind: "ready", items: await getHouseholdEvidence(householdId) });
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
        setEvidenceState({ kind: "auth-required" });
      } else if (error instanceof ApiError && error.status === 403) {
        setEvidenceState({ kind: "forbidden" });
      } else {
        setEvidenceState({ kind: "error" });
      }
    }
  }, [householdId]);

  useEffect(() => {
    let mounted = true;
    setHouseholdState({ kind: "loading" });
    getHousehold(householdId)
      .then((item) => {
        if (mounted) setHouseholdState({ kind: "ready", item });
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
          setHouseholdState({ kind: "auth-required" });
        } else if (error instanceof ApiError && error.status === 404) {
          setHouseholdState({ kind: "not-found" });
        } else {
          setHouseholdState({ kind: "error" });
        }
      });
    return () => {
      mounted = false;
    };
  }, [householdId]);

  useEffect(() => {
    void loadEvidence();
  }, [loadEvidence]);

  const evidenceItems = evidenceState.kind === "ready" ? evidenceState.items : [];
  const visibleItems = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return evidenceItems.filter((item) => {
      if (normalizedQuery && !item.title.toLocaleLowerCase().includes(normalizedQuery)) {
        return false;
      }
      if (filter === "PROCESSING") return isProcessing(item);
      if (filter === "AVAILABLE") return isAvailable(item);
      if (filter === "BLOCKED") return isBlocked(item);
      return true;
    });
  }, [evidenceItems, filter, query]);

  const metrics = useMemo(() => ({
    total: evidenceItems.length,
    available: evidenceItems.filter(isAvailable).length,
    processing: evidenceItems.filter(isProcessing).length,
    blocked: evidenceItems.filter(isBlocked).length,
  }), [evidenceItems]);

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || file === null || title.trim().length === 0) return;
    if (evidenceType === "" || sensitivity === "") {
      setActionError("نوع مدرک و سطح حساسیت را پیش از بارگذاری انتخاب کنید.");
      setActionSuccess(null);
      return;
    }
    const mediaType = mediaTypeFor(file);
    if (!allowedMediaTypes.has(mediaType)) {
      setActionError("فقط فایل‌های PDF، PNG، JPG و TXT در این بخش پذیرفته می‌شوند.");
      setActionSuccess(null);
      return;
    }
    if (file.size <= 0 || file.size > MAX_UPLOAD_BYTES) {
      setActionError("حجم فایل باید بیشتر از صفر و حداکثر ۱۰ مگابایت باشد.");
      setActionSuccess(null);
      return;
    }

    setBusy(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      setStage("hashing");
      const expectedSha256 = await sha256Hex(file);
      setStage("initiating");
      const initialized = await initEvidenceUpload(householdId, {
        evidence_type: evidenceType,
        title: title.trim(),
        description: description.trim() || null,
        original_filename: file.name,
        media_type: mediaType,
        size_bytes: file.size,
        sensitivity_class: sensitivity,
      });
      setStage("uploading");
      await uploadEvidenceContent(initialized.upload_url, file, mediaType);
      setStage("scanning");
      const finalized = await finalizeEvidence(initialized.evidence.id, expectedSha256);
      if (finalized.lifecycle_status === "AVAILABLE" && finalized.scan_status === "CLEAN") {
        setActionSuccess("مدرک ثبت و بررسی امنیتی شد؛ دسترسی به آن همچنان تابع مجوز سازمانی است.");
      } else if (finalized.lifecycle_status === "QUARANTINED") {
        setActionSuccess("مدرک پس از اسکن در قرنطینه قرار گرفت. دانلود آن مسدود است.");
      } else {
        setActionSuccess("مدرک ثبت شد، اما بررسی امنیتی آن کامل نشده است؛ تا تعیین وضعیت قابل دانلود نیست.");
      }
      setTitle("");
      setDescription("");
      setEvidenceType("");
      setSensitivity("");
      setFile(null);
      setFileInputVersion((value) => value + 1);
      await loadEvidence();
    } catch (error: unknown) {
      setActionError(actionErrorMessage(error));
      await loadEvidence();
    } finally {
      setBusy(false);
      setStage(null);
    }
  }

  async function downloadEvidence(item: EvidenceRecord) {
    if (!isAvailable(item) || downloadingId !== null) return;
    setDownloadingId(item.id);
    setDownloadError(null);
    try {
      const target = await getEvidenceDownloadTarget(item.id);
      const anchor = document.createElement("a");
      anchor.href = `${hamoonRuntimeConfig.apiBaseUrl}${target.download_url}`;
      anchor.rel = "noreferrer";
      anchor.download = "";
      anchor.style.display = "none";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } catch (error: unknown) {
      setDownloadError(actionErrorMessage(error));
    } finally {
      setDownloadingId(null);
    }
  }

  if (householdState.kind === "loading") return <LoadingState label="در حال دریافت پرونده و مجوزها…" />;
  if (householdState.kind === "auth-required") {
    return <EmptyState title="ورود سازمانی لازم است" description="برای مشاهده مدارک باید ورود سازمانی معتبر داشته باشید." />;
  }
  if (householdState.kind === "not-found") {
    return <ErrorState title="پرونده در دسترس نیست" description="پرونده وجود ندارد یا دسترسی شما به آن مجاز نیست." action={<AppLink className="hm-button hm-button--secondary" to="/households">بازگشت به پرونده‌ها</AppLink>} />;
  }
  if (householdState.kind === "error") {
    return <ErrorState title="دریافت پرونده ناموفق بود" description="اطلاعات پرونده دریافت نشد." />;
  }

  const household = householdState.item;

  return (
    <div className="page-stack evidence-page">
      <header className="page-heading evidence-page__heading">
        <div>
          <AppLink className="text-link" to={`/households/${household.id}`}>پرونده خانوار ←</AppLink>
          <span className="eyebrow">پرونده‌های من / خانوار امدادی / مدارک و مستندات</span>
          <h1>مدارک و مستندات خانوار</h1>
          <p>مدارک فقط از مسیر امن بارگذاری می‌شوند؛ فایل پس از ثبت، بررسی یکپارچگی و اسکن امنیتی قابل دسترسی خواهد شد.</p>
        </div>
        <Badge tone="accent">پرونده {household.case_code}</Badge>
      </header>

      <section className="metric-grid evidence-metrics" aria-label="خلاصه مدارک">
        <MetricCard label="مدارک قابل مشاهده (حداکثر ۲۰۰)" value={evidenceState.kind === "ready" ? metrics.total : "—"} />
        <MetricCard label="در دسترس" value={evidenceState.kind === "ready" ? metrics.available : "—"} />
        <MetricCard label="در انتظار بررسی" value={evidenceState.kind === "ready" ? metrics.processing : "—"} />
        <MetricCard label="مسدود یا بایگانی" value={evidenceState.kind === "ready" ? metrics.blocked : "—"} />
      </section>

      <div className="evidence-workspace-grid">
        <Panel className="evidence-upload-panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">بارگذاری امن و ثبت‌شده</span>
              <h2>بارگذاری مدرک جدید</h2>
            </div>
            <Badge tone="accent">ثبت رویداد و حسابرسی</Badge>
          </div>
          <p className="evidence-intro">نوع مدرک و سطح حساسیت را انتخاب کنید. فایل قبل از دسترس‌پذیری از نظر یکپارچگی و امنیت بررسی می‌شود.</p>

          <form className="evidence-upload-form" onSubmit={(event) => void submitUpload(event)}>
            <div className="evidence-form-grid">
              <label>
                <span>عنوان مدرک</span>
                <input
                  required
                  maxLength={250}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="عنوان قابل تشخیص مدرک"
                />
              </label>
              <label>
                <span>نوع مدرک</span>
                <select required value={evidenceType} onChange={(event) => setEvidenceType(event.target.value as EvidenceType | "")}>
                  <option value="">انتخاب نوع مدرک</option>
                  {Object.entries(evidenceTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label>
                <span>سطح حساسیت</span>
                <select required value={sensitivity} onChange={(event) => setSensitivity(event.target.value as EvidenceSensitivity | "")}>
                  <option value="">انتخاب سطح حساسیت</option>
                  {Object.entries(sensitivityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="evidence-description-field">
                <span>توضیح (اختیاری)</span>
                <textarea rows={2} maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="توضیح کوتاه درباره مدرک" />
              </label>
            </div>

            <label className="evidence-dropzone" htmlFor="evidence-file">
              <span className="evidence-dropzone__icon" aria-hidden="true">↑</span>
              <strong>{file ? file.name : "برای انتخاب فایل کلیک کنید"}</strong>
              <span>{file ? sizeLabel(file.size) : "PDF، PNG، JPG یا TXT · حداکثر ۱۰ مگابایت"}</span>
              <input
                key={fileInputVersion}
                id="evidence-file"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.txt,application/pdf,image/png,image/jpeg,text/plain"
                onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] ?? null)}
                disabled={busy}
              />
            </label>

            {actionError ? <div className="inline-alert" role="alert">{actionError}</div> : null}
            {actionSuccess ? <div className="evidence-success" role="status">{actionSuccess}</div> : null}
            {busy ? (
              <div className="evidence-upload-progress" role="status" aria-live="polite">
                <LoadingState label={
                  stage === "hashing" ? "در حال محاسبه اثر انگشت فایل…"
                    : stage === "initiating" ? "در حال ایجاد نشست امن بارگذاری…"
                      : stage === "uploading" ? "در حال بارگذاری فایل…"
                        : "در حال بررسی یکپارچگی و اسکن امنیتی…"
                } />
              </div>
            ) : null}
            <div className="evidence-form-actions">
              <Button type="submit" disabled={busy || file === null || title.trim().length === 0 || evidenceType === "" || sensitivity === ""}>
                {busy ? "در حال ثبت مدرک…" : "بارگذاری و بررسی"}
              </Button>
              <span>فقط فایل‌های مجاز؛ لینک بارگذاری کوتاه‌عمر و یک‌بارمصرف است.</span>
            </div>
          </form>
        </Panel>

        <Panel className="evidence-privacy-panel">
          <Badge tone="accent">حریم خصوصی و کنترل دسترسی</Badge>
          <h2>مدارک امن می‌مانند</h2>
          <ul>
            <li>مدارک حساس فقط برای نقش‌ها و مجوزهای مجاز قابل مشاهده‌اند.</li>
            <li>فایل تا پایان اسکن موفق قابل دانلود نیست.</li>
            <li>مدرک قرنطینه‌شده یا دارای خطای اسکن از مسیر دانلود مسدود است.</li>
            <li>نشست بارگذاری و لینک دانلود، محدود به زمان و قابلیت امضاشده هستند.</li>
          </ul>
        </Panel>
      </div>

      <Panel className="evidence-list-panel">
        <div className="section-heading evidence-list-heading">
          <div>
            <span className="eyebrow">فهرست متصل به داده واقعی</span>
            <h2>فهرست مدارک</h2>
            <p>مدارکی که طبق سطح دسترسی سازمانی برای شما قابل مشاهده‌اند.</p>
          </div>
          <Button variant="secondary" onClick={() => void loadEvidence()} disabled={evidenceState.kind === "loading"}>
            تازه‌سازی فهرست
          </Button>
        </div>
        {downloadError ? <div className="inline-alert" role="alert">{downloadError}</div> : null}

        <div className="evidence-list-controls">
          <label className="evidence-search">
            <span>جست‌وجوی عنوان مدرک</span>
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="جست‌وجو در مدارک قابل مشاهده" />
          </label>
          <div className="evidence-status-filters" aria-label="فیلتر وضعیت مدارک">
            {([
              ["ALL", "همه"],
              ["AVAILABLE", "در دسترس"],
              ["PROCESSING", "در حال بررسی"],
              ["BLOCKED", "نیازمند بررسی"],
            ] as const).map(([value, label]) => (
              <button key={value} type="button" className={filter === value ? "evidence-filter is-active" : "evidence-filter"} aria-pressed={filter === value} onClick={() => setFilter(value)}>
                {label}
              </button>
            ))}
          </div>
        </div>

        {evidenceState.kind === "loading" ? <LoadingState label="در حال دریافت فهرست مدارک…" /> : null}
        {evidenceState.kind === "auth-required" ? <EmptyState title="ورود سازمانی لازم است" description="برای دریافت فهرست مدارک، ورود سازمانی معتبر لازم است." /> : null}
        {evidenceState.kind === "forbidden" ? <ErrorState title="دسترسی مجاز نیست" description="این فهرست برای نقش یا دامنه دسترسی فعلی قابل مشاهده نیست." /> : null}
        {evidenceState.kind === "error" ? <ErrorState description="فهرست مدارک دریافت نشد." action={<Button variant="secondary" onClick={() => void loadEvidence()}>تلاش دوباره</Button>} /> : null}
        {evidenceState.kind === "ready" && visibleItems.length === 0 ? (
          <EmptyState title={evidenceItems.length === 0 ? "مدرکی ثبت نشده است" : "مدرکی مطابق فیلتر پیدا نشد"} description={evidenceItems.length === 0 ? "پس از بارگذاری امن، وضعیت بررسی و دسترسی هر مدرک در همین فهرست نمایش داده می‌شود." : "عبارت جست‌وجو یا فیلتر وضعیت را تغییر دهید."} />
        ) : null}
        {evidenceState.kind === "ready" && visibleItems.length > 0 ? (
          <div className="evidence-table-wrap">
            <table className="evidence-table">
              <thead>
                <tr>
                  <th scope="col">عنوان مدرک</th>
                  <th scope="col">نوع مدرک</th>
                  <th scope="col">تاریخ ثبت</th>
                  <th scope="col">حساسیت</th>
                  <th scope="col">وضعیت</th>
                  <th scope="col">حجم</th>
                  <th scope="col">اقدام</th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.title}</strong>
                      <span className="evidence-row__meta">{item.media_type}</span>
                    </td>
                    <td>{evidenceTypeLabels[item.evidence_type]}</td>
                    <td>{recordedAtFormatter.format(new Date(item.recorded_at))}</td>
                    <td>{sensitivityLabels[item.sensitivity_class]}</td>
                    <td><Badge tone={lifecycleTone(item)}>{lifecycleLabels[item.lifecycle_status]}</Badge></td>
                    <td>{sizeLabel(item.size_bytes ?? item.expected_size_bytes)}</td>
                    <td>
                      {isAvailable(item) ? (
                        <Button variant="secondary" disabled={downloadingId !== null} onClick={() => void downloadEvidence(item)}>
                          {downloadingId === item.id ? "در حال آماده‌سازی…" : "دانلود"}
                        </Button>
                      ) : (
                        <span className="evidence-no-download">
                          {item.lifecycle_status === "QUARANTINED" ? "مسدود · قرنطینه" : "تا تأیید اسکن"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <p className="evidence-audit-note">بارگذاری، ثبت نهایی و درخواست دانلود در مسیرهای حسابرسی سامانه ثبت می‌شوند.</p>
      </Panel>
    </div>
  );
}
