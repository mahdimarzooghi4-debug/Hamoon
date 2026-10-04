import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import { ApiError } from "../api/client";
import {
  listDiagnoses,
  type DiagnosisHistoryEntry,
  type HumanDecisionAction,
} from "../api/diagnosis";
import {
  activatePrescriptionItem,
  generatePrescription,
  listPrescriptions,
  reviewPrescription,
  type InterventionType,
  type PrescriptionHistoryEntry,
  type PrescriptionProposal,
  type PrescriptionStatus,
} from "../api/prescriptions";
import type { PGORVariable } from "../api/households";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
} from "../design-system/components";

type State =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "error"; message: string }
  | {
      kind: "ready";
      prescriptions: PrescriptionHistoryEntry[];
      diagnoses: DiagnosisHistoryEntry[];
    };

type ReviewAction = Extract<
  HumanDecisionAction,
  "CONFIRM" | "MODIFY" | "REPLACE" | "DEFER"
>;

interface DraftItem {
  code: string;
  targetVariable: PGORVariable;
  interventionType: InterventionType;
  priorityRank: number;
  title: string;
  rationale: string;
  successCriteria: string;
  reviewAfterDays: number;
  reviewRationale: string;
  diagnosisRefs: string;
  supportingRefs: string;
}

interface DraftPrescription {
  summary: string;
  intensityScore: string;
  items: DraftItem[];
  reviewFlags: string;
}

const acceptedDiagnosisStatuses = new Set(["CONFIRMED", "MODIFIED", "REPLACED"]);

const statusLabels: Record<PrescriptionStatus, string> = {
  UNDER_REVIEW: "نیازمند تصمیم مددکار",
  APPROVED: "تأییدشده",
  MODIFIED: "اصلاح‌شده",
  REPLACED: "جایگزین‌شده",
  DEFERRED: "به تعویق افتاده",
};

const actionLabels: Record<ReviewAction, string> = {
  CONFIRM: "تأیید نسخه پیشنهادی",
  MODIFY: "اصلاح نسخه",
  REPLACE: "جایگزینی نسخه",
  DEFER: "بررسی نسخه در زمان دیگر",
};

const variableLabels: Record<PGORVariable, string> = {
  P: "مشارکت",
  G: "ظرفیت رشد",
  O: "فرصت",
  R: "تاب‌آوری",
};

const interventionLabels: Record<InterventionType, string> = {
  COUNSELING: "مشاوره",
  MOTIVATION: "انگیزشی",
  PSYCHOLOGICAL_EMPOWERMENT: "توانمندسازی روانی",
  COACHING: "مربی‌گری",
  TRAINING: "آموزش",
  SKILLS_TRAINING: "آموزش مهارت",
  VOCATIONAL_TRAINING: "آموزش فنی",
  MARKET_LINKAGE: "اتصال به بازار",
  EMPLOYMENT: "اشتغال",
  FINANCING_FACILITIES: "تسهیلات",
  NETWORKING: "شبکه‌سازی",
  SOCIAL_SUPPORT: "حمایت اجتماعی",
  TREATMENT: "درمان",
  RISK_REDUCTION: "کاهش ریسک",
  STABILIZATION: "تثبیت",
};

const interventionTypes = Object.keys(interventionLabels) as InterventionType[];

const defaultReasonCodes: Record<ReviewAction, string> = {
  CONFIRM: "CONFIRMED_AS_IS",
  MODIFY: "PROFESSIONAL_JUDGMENT",
  REPLACE: "REPLACEMENT_REQUIRED",
  DEFER: "MORE_REVIEW_REQUIRED",
};

const persianDateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function statusTone(
  status: PrescriptionStatus,
): "accent" | "success" | "warning" | "neutral" {
  if (status === "APPROVED" || status === "MODIFIED" || status === "REPLACED") {
    return "success";
  }
  if (status === "DEFERRED") return "warning";
  return "accent";
}

function canReview(status: PrescriptionStatus): boolean {
  return status === "UNDER_REVIEW" || status === "DEFERRED";
}

function csv(values: string[]): string {
  return values.join(", ");
}

function uniqueCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
}

function lines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function proposalToDraft(proposal: PrescriptionProposal): DraftPrescription {
  return {
    summary: proposal.summary,
    intensityScore: proposal.intensity_score,
    items: proposal.items.map((item) => ({
      code: item.code,
      targetVariable: item.target_variable,
      interventionType: item.intervention_type,
      priorityRank: item.priority_rank,
      title: item.title,
      rationale: item.rationale,
      successCriteria: item.success_criteria.join("\n"),
      reviewAfterDays: item.review_schedule.review_after_days,
      reviewRationale: item.review_schedule.rationale,
      diagnosisRefs: csv(item.diagnosis_refs),
      supportingRefs: csv(item.supporting_feature_refs),
    })),
    reviewFlags: csv(
      proposal.review_flags.filter((flag) => flag !== "HUMAN_REVIEW_REQUIRED"),
    ),
  };
}

function draftToProposal(draft: DraftPrescription): PrescriptionProposal {
  return {
    schema_version: "prescription-v1",
    summary: draft.summary.trim(),
    intensity_score: draft.intensityScore.trim(),
    items: draft.items.map((item) => ({
      code: item.code.trim(),
      target_variable: item.targetVariable,
      intervention_type: item.interventionType,
      priority_rank: item.priorityRank,
      title: item.title.trim(),
      rationale: item.rationale.trim(),
      success_criteria: lines(item.successCriteria),
      review_schedule: {
        review_after_days: item.reviewAfterDays,
        rationale: item.reviewRationale.trim(),
      },
      diagnosis_refs: uniqueCsv(item.diagnosisRefs),
      supporting_feature_refs: uniqueCsv(item.supportingRefs),
    })),
    review_flags: [
      "HUMAN_REVIEW_REQUIRED",
      ...uniqueCsv(draft.reviewFlags).filter(
        (flag) => flag !== "HUMAN_REVIEW_REQUIRED",
      ),
    ],
  };
}

function validateDraft(draft: DraftPrescription): string | null {
  const intensity = Number(draft.intensityScore);
  if (
    draft.summary.trim().length === 0 ||
    !Number.isFinite(intensity) ||
    intensity < 0 ||
    intensity > 1
  ) {
    return "خلاصه نسخه و شدت مداخله بین صفر تا یک باید معتبر باشند.";
  }
  if (draft.items.length === 0) {
    return "نسخه باید حداقل یک مداخله داشته باشد.";
  }
  const priorities = draft.items.map((item) => item.priorityRank);
  if (new Set(priorities).size !== priorities.length) {
    return "اولویت مداخلات باید یکتا باشد.";
  }
  for (const item of draft.items) {
    if (
      item.code.trim().length === 0 ||
      item.title.trim().length === 0 ||
      item.rationale.trim().length === 0 ||
      item.reviewRationale.trim().length === 0 ||
      item.priorityRank < 1 ||
      item.priorityRank > 20 ||
      item.reviewAfterDays < 1 ||
      item.reviewAfterDays > 730 ||
      lines(item.successCriteria).length === 0 ||
      uniqueCsv(item.diagnosisRefs).length === 0 ||
      uniqueCsv(item.supportingRefs).length === 0
    ) {
      return "کد، عنوان، استدلال، معیار موفقیت، زمان بازبینی و ارجاع‌های هر مداخله باید کامل باشند.";
    }
  }
  return null;
}

export function PrescriptionSection({
  householdId,
  pgorSnapshotId,
}: {
  householdId: string;
  pgorSnapshotId: string | null;
}) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [reviewAction, setReviewAction] = useState<ReviewAction | null>(null);
  const [reasonCode, setReasonCode] = useState("");
  const [reasonText, setReasonText] = useState("");
  const [draft, setDraft] = useState<DraftPrescription | null>(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activatingItemId, setActivatingItemId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const [prescriptions, diagnoses] = await Promise.all([
        listPrescriptions(householdId),
        listDiagnoses(householdId),
      ]);
      setState({ kind: "ready", prescriptions, diagnoses });
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
        setState({ kind: "auth-required" });
      } else {
        setState({ kind: "error", message: "نسخه‌های توانمندسازی دریافت نشدند." });
      }
    }
  }, [householdId]);

  useEffect(() => {
    void load();
  }, [load]);

  const prescriptions =
    state.kind === "ready" ? state.prescriptions : [];
  const diagnoses = state.kind === "ready" ? state.diagnoses : [];
  const latest = prescriptions[0] ?? null;
  const latestDiagnosis = diagnoses[0] ?? null;
  const eligibleDiagnosis =
    latestDiagnosis !== null &&
    acceptedDiagnosisStatuses.has(latestDiagnosis.status) &&
    latestDiagnosis.accepted_payload !== null
      ? latestDiagnosis
      : null;

  const displayedProposal = useMemo(() => {
    if (latest === null) return null;
    return latest.accepted_payload ?? latest.machine_proposal;
  }, [latest]);

  async function handleGenerate() {
    if (eligibleDiagnosis === null || pgorSnapshotId === null) return;
    setGenerating(true);
    setActionError(null);
    try {
      await generatePrescription(
        householdId,
        eligibleDiagnosis.id,
        pgorSnapshotId,
      );
      await load();
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        setActionError(
          error.code === "ACCEPTED_DIAGNOSIS_REQUIRED"
            ? "آخرین تشخیص هنوز برای تولید نسخه نهایی نشده است."
            : error.code === "DIAGNOSIS_SNAPSHOT_MISMATCH"
              ? "تشخیص و PGOR جاری از یک snapshot نیستند؛ ابتدا state پرونده را تازه کنید."
              : error.code === "AI_PROVIDER_UNAVAILABLE"
                ? "سرویس پیشنهاد نسخه در دسترس نیست."
                : "ساخت پیشنهاد نسخه انجام نشد.",
        );
      } else {
        setActionError("ساخت پیشنهاد نسخه انجام نشد.");
      }
    } finally {
      setGenerating(false);
    }
  }

  function openReview(action: ReviewAction) {
    if (latest === null) return;
    setActionError(null);
    setReviewAction(action);
    setReasonCode(defaultReasonCodes[action]);
    setReasonText("");
    setDraft(
      action === "MODIFY" || action === "REPLACE"
        ? proposalToDraft(latest.accepted_payload ?? latest.machine_proposal)
        : null,
    );
  }

  function closeReview() {
    if (saving) return;
    setReviewAction(null);
    setDraft(null);
    setReasonCode("");
    setReasonText("");
    setActionError(null);
  }

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (latest === null || reviewAction === null) return;

    const structured =
      reviewAction === "MODIFY" || reviewAction === "REPLACE";
    if (structured && draft !== null) {
      const error = validateDraft(draft);
      if (error !== null) {
        setActionError(error);
        return;
      }
    }
    if (structured && reasonText.trim().length === 0) {
      setActionError("برای تغییر نسخه، توضیح حرفه‌ای مددکار الزامی است.");
      return;
    }

    setSaving(true);
    setActionError(null);
    try {
      await reviewPrescription(latest, reviewAction, {
        reasonCode: reasonCode.trim() || null,
        reasonText: reasonText.trim() || null,
        modifiedPayload:
          structured && draft !== null ? draftToProposal(draft) : undefined,
      });
      setReviewAction(null);
      setDraft(null);
      await load();
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        setActionError(
          "این نسخه هم‌زمان تغییر کرده است. اطلاعات تازه بارگذاری شد؛ تصمیم را دوباره بررسی کنید.",
        );
        await load();
      } else if (error instanceof ApiError && error.status === 422) {
        setActionError(
          "نسخه اصلاح‌شده با قواعد ساختاری یا شواهد پرونده سازگار نیست.",
        );
      } else {
        setActionError("ثبت تصمیم درباره نسخه انجام نشد.");
      }
    } finally {
      setSaving(false);
    }
  }

  function updateDraftItem(index: number, patch: Partial<DraftItem>) {
    setDraft((current) =>
      current === null
        ? current
        : {
            ...current,
            items: current.items.map((item, itemIndex) =>
              itemIndex === index ? { ...item, ...patch } : item,
            ),
          },
    );
  }

  function addDraftItem() {
    if (eligibleDiagnosis === null) return;
    setDraft((current) => {
      if (current === null) return current;
      const nextPriority =
        current.items.length === 0
          ? 1
          : Math.min(20, Math.max(...current.items.map((item) => item.priorityRank)) + 1);
      return {
        ...current,
        items: [
          ...current.items,
          {
            code: "",
            targetVariable: "O",
            interventionType: "NETWORKING",
            priorityRank: nextPriority,
            title: "",
            rationale: "",
            successCriteria: "",
            reviewAfterDays: 30,
            reviewRationale: "",
            diagnosisRefs: `diagnosis:${eligibleDiagnosis.id}`,
            supportingRefs: "",
          },
        ],
      };
    });
  }

  async function activateItem(itemId: string) {
    if (latest === null) return;
    setActivatingItemId(itemId);
    setActionError(null);
    try {
      await activatePrescriptionItem(latest.id, itemId);
      await load();
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 422) {
        setActionError(
          "این مداخله در وضعیت فعلی قابل فعال‌سازی نیست یا قبلاً فعال شده است.",
        );
      } else {
        setActionError("فعال‌سازی مداخله انجام نشد.");
      }
    } finally {
      setActivatingItemId(null);
    }
  }

  return (
    <Panel className="prescription-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">از تشخیص نهایی به اقدام قابل‌سنجش</span>
          <h2>نسخه توانمندسازی</h2>
        </div>
        {latest ? (
          <Badge tone={statusTone(latest.status)}>
            {statusLabels[latest.status]}
          </Badge>
        ) : null}
      </div>

      {actionError ? (
        <div className="inline-alert" role="alert">{actionError}</div>
      ) : null}

      {state.kind === "loading" ? (
        <LoadingState label="در حال دریافت نسخه…" />
      ) : null}

      {state.kind === "auth-required" ? (
        <EmptyState
          title="ورود سازمانی لازم است"
          description="نسخه بدون احراز هویت از API خوانده نمی‌شود."
        />
      ) : null}

      {state.kind === "error" ? (
        <ErrorState
          description={state.message}
          action={
            <Button variant="secondary" onClick={() => void load()}>
              تلاش دوباره
            </Button>
          }
        />
      ) : null}

      {state.kind === "ready" && latest === null ? (
        <div className="prescription-empty">
          <EmptyState
            title="نسخه‌ای برای این پرونده ثبت نشده است"
            description={
              pgorSnapshotId === null
                ? "برای تولید نسخه باید PGOR رسمی موجود باشد."
                : eligibleDiagnosis === null
                  ? "ابتدا آخرین تشخیص باید با تصمیم انسانی نهایی شود."
                  : "نسخه از آخرین تشخیص نهایی و همان PGOR رسمی ساخته می‌شود."
            }
          />
          {pgorSnapshotId !== null && eligibleDiagnosis !== null ? (
            <Button disabled={generating} onClick={() => void handleGenerate()}>
              {generating ? "در حال ساخت نسخه…" : "ساخت نسخه پیشنهادی"}
            </Button>
          ) : null}
        </div>
      ) : null}

      {state.kind === "ready" && latest !== null && displayedProposal !== null ? (
        <>
          <div className="prescription-current">
            <div className="prescription-summary">
              <div className="prescription-summary__meta">
                <Badge tone="accent">پیشنهاد نسخه هامون</Badge>
                <span>{latest.model_alias}</span>
                <span>{persianDateTime.format(new Date(latest.generated_at))}</span>
              </div>
              <h3>{displayedProposal.summary}</h3>
              <div className="prescription-intensity">
                <span>شدت مداخله</span>
                <strong>
                  {Number(displayedProposal.intensity_score).toLocaleString("fa-IR", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </strong>
              </div>
            </div>

            <div className="prescription-items">
              {displayedProposal.items.map((item) => (
                <article className="prescription-item" key={item.code}>
                  <div className="prescription-item__top">
                    <Badge tone="accent">
                      اولویت {item.priority_rank.toLocaleString("fa-IR")}
                    </Badge>
                    <Badge tone="neutral">
                      {variableLabels[item.target_variable]} — {item.target_variable}
                    </Badge>
                  </div>
                  <strong>{item.title}</strong>
                  <span>{interventionLabels[item.intervention_type]}</span>
                  <p>{item.rationale}</p>
                  <div className="prescription-item__facts">
                    <div>
                      <span>بازبینی</span>
                      <strong>
                        {item.review_schedule.review_after_days.toLocaleString("fa-IR")} روز
                      </strong>
                    </div>
                    <div>
                      <span>معیار موفقیت</span>
                      <strong>{item.success_criteria.join("، ")}</strong>
                    </div>
                  </div>
                </article>
              ))}
            </div>

            {displayedProposal.review_flags.length > 0 ? (
              <div className="prescription-flags">
                {displayedProposal.review_flags.map((flag) => (
                  <Badge
                    key={flag}
                    tone={flag === "HUMAN_REVIEW_REQUIRED" ? "warning" : "neutral"}
                  >
                    {flag === "HUMAN_REVIEW_REQUIRED"
                      ? "بازبینی انسانی الزامی"
                      : flag}
                  </Badge>
                ))}
              </div>
            ) : null}

            {canReview(latest.status) ? (
              <div className="prescription-actions">
                <Button onClick={() => openReview("CONFIRM")}>
                  تأیید نسخه
                </Button>
                <Button variant="secondary" onClick={() => openReview("MODIFY")}>
                  اصلاح / افزودن مداخله
                </Button>
                <Button variant="secondary" onClick={() => openReview("REPLACE")}>
                  جایگزینی نسخه
                </Button>
                <Button variant="quiet" onClick={() => openReview("DEFER")}>
                  بررسی بعدی
                </Button>
              </div>
            ) : null}
          </div>

          {reviewAction !== null ? (
            <form className="prescription-review-form" onSubmit={submitReview}>
              <div className="prescription-review-form__heading">
                <div>
                  <span className="eyebrow">تصمیم نهایی با مددکار</span>
                  <h3>{actionLabels[reviewAction]}</h3>
                </div>
                <button
                  aria-label="بستن"
                  className="drawer-close"
                  onClick={closeReview}
                  type="button"
                >
                  ×
                </button>
              </div>

              <div className="form-grid">
                <label>
                  <span>کد دلیل</span>
                  <input
                    maxLength={100}
                    onChange={(event) => setReasonCode(event.target.value)}
                    value={reasonCode}
                  />
                </label>
                <label className="form-grid__wide">
                  <span>
                    توضیح مددکار
                    {reviewAction === "CONFIRM" || reviewAction === "DEFER"
                      ? " (اختیاری)"
                      : ""}
                  </span>
                  <textarea
                    maxLength={1000}
                    onChange={(event) => setReasonText(event.target.value)}
                    rows={3}
                    value={reasonText}
                  />
                </label>
              </div>

              {(reviewAction === "MODIFY" || reviewAction === "REPLACE") &&
              draft !== null ? (
                <div className="prescription-editor">
                  <div className="form-grid">
                    <label className="form-grid__wide">
                      <span>خلاصه نسخه نهایی</span>
                      <textarea
                        maxLength={2000}
                        onChange={(event) =>
                          setDraft((current) =>
                            current === null
                              ? current
                              : { ...current, summary: event.target.value },
                          )
                        }
                        rows={3}
                        value={draft.summary}
                      />
                    </label>
                    <label>
                      <span>شدت مداخله، صفر تا یک</span>
                      <input
                        inputMode="decimal"
                        max="1"
                        min="0"
                        onChange={(event) =>
                          setDraft((current) =>
                            current === null
                              ? current
                              : { ...current, intensityScore: event.target.value },
                          )
                        }
                        step="0.01"
                        type="number"
                        value={draft.intensityScore}
                      />
                    </label>
                    <label>
                      <span>پرچم‌های تکمیلی، جداشده با ویرگول</span>
                      <input
                        onChange={(event) =>
                          setDraft((current) =>
                            current === null
                              ? current
                              : { ...current, reviewFlags: event.target.value },
                          )
                        }
                        value={draft.reviewFlags}
                      />
                    </label>
                  </div>

                  <div className="prescription-editor__items">
                    {draft.items.map((item, index) => (
                      <div className="prescription-editor-item" key={index}>
                        <div className="prescription-editor-item__top">
                          <strong>
                            مداخله {(index + 1).toLocaleString("fa-IR")}
                          </strong>
                          {draft.items.length > 1 ? (
                            <Button
                              type="button"
                              variant="quiet"
                              onClick={() =>
                                setDraft((current) =>
                                  current === null
                                    ? current
                                    : {
                                        ...current,
                                        items: current.items.filter(
                                          (_, itemIndex) => itemIndex !== index,
                                        ),
                                      },
                                )
                              }
                            >
                              حذف
                            </Button>
                          ) : null}
                        </div>

                        <div className="form-grid">
                          <label>
                            <span>کد مداخله</span>
                            <input
                              maxLength={150}
                              onChange={(event) =>
                                updateDraftItem(index, { code: event.target.value })
                              }
                              value={item.code}
                            />
                          </label>
                          <label>
                            <span>اولویت</span>
                            <input
                              max={20}
                              min={1}
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  priorityRank: Number(event.target.value),
                                })
                              }
                              type="number"
                              value={item.priorityRank}
                            />
                          </label>
                          <label>
                            <span>متغیر هدف PGOR</span>
                            <select
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  targetVariable: event.target.value as PGORVariable,
                                })
                              }
                              value={item.targetVariable}
                            >
                              {(["P", "G", "O", "R"] as PGORVariable[]).map((value) => (
                                <option key={value} value={value}>
                                  {variableLabels[value]} — {value}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            <span>نوع مداخله</span>
                            <select
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  interventionType: event.target.value as InterventionType,
                                })
                              }
                              value={item.interventionType}
                            >
                              {interventionTypes.map((value) => (
                                <option key={value} value={value}>
                                  {interventionLabels[value]}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="form-grid__wide">
                            <span>عنوان</span>
                            <input
                              maxLength={300}
                              onChange={(event) =>
                                updateDraftItem(index, { title: event.target.value })
                              }
                              value={item.title}
                            />
                          </label>
                          <label className="form-grid__wide">
                            <span>استدلال</span>
                            <textarea
                              maxLength={2000}
                              onChange={(event) =>
                                updateDraftItem(index, { rationale: event.target.value })
                              }
                              rows={3}
                              value={item.rationale}
                            />
                          </label>
                          <label className="form-grid__wide">
                            <span>معیارهای موفقیت؛ هر خط یک معیار</span>
                            <textarea
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  successCriteria: event.target.value,
                                })
                              }
                              rows={3}
                              value={item.successCriteria}
                            />
                          </label>
                          <label>
                            <span>بازبینی پس از چند روز</span>
                            <input
                              max={730}
                              min={1}
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  reviewAfterDays: Number(event.target.value),
                                })
                              }
                              type="number"
                              value={item.reviewAfterDays}
                            />
                          </label>
                          <label>
                            <span>دلیل زمان بازبینی</span>
                            <input
                              maxLength={1000}
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  reviewRationale: event.target.value,
                                })
                              }
                              value={item.reviewRationale}
                            />
                          </label>
                          <label className="form-grid__wide">
                            <span>ارجاع‌های تشخیص، جداشده با ویرگول</span>
                            <input
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  diagnosisRefs: event.target.value,
                                })
                              }
                              value={item.diagnosisRefs}
                            />
                          </label>
                          <label className="form-grid__wide">
                            <span>ارجاع‌های داده پشتیبان، جداشده با ویرگول</span>
                            <input
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  supportingRefs: event.target.value,
                                })
                              }
                              value={item.supportingRefs}
                            />
                          </label>
                        </div>
                      </div>
                    ))}
                  </div>

                  <Button type="button" variant="secondary" onClick={addDraftItem}>
                    افزودن مداخله
                  </Button>
                </div>
              ) : null}

              <div className="prescription-review-form__actions">
                <Button disabled={saving} type="submit">
                  {saving ? "در حال ثبت…" : "ثبت تصمیم نسخه"}
                </Button>
                <Button
                  disabled={saving}
                  type="button"
                  variant="secondary"
                  onClick={closeReview}
                >
                  انصراف
                </Button>
              </div>
            </form>
          ) : null}

          {latest.accepted_items.length > 0 ? (
            <div className="accepted-interventions">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">آیتم‌های پذیرفته‌شده نسخه</span>
                  <h3>مداخلات آماده اجرا</h3>
                </div>
              </div>
              <div className="accepted-interventions__list">
                {latest.accepted_items.map((item) => (
                  <article className="accepted-intervention" key={item.id}>
                    <div>
                      <strong>{item.title}</strong>
                      <span>
                        {interventionLabels[item.intervention_type]} • هدف{" "}
                        {variableLabels[item.target_pgor_variable]}
                      </span>
                    </div>
                    <div className="accepted-intervention__actions">
                      <Badge tone={item.status === "ACTIVATED" ? "success" : "neutral"}>
                        {item.status === "ACTIVATED"
                          ? "فعال شده"
                          : item.status === "SUPERSEDED"
                            ? "جایگزین شده"
                            : "پذیرفته شده"}
                      </Badge>
                      {item.status === "ACCEPTED" ? (
                        <Button
                          disabled={activatingItemId === item.id}
                          onClick={() => void activateItem(item.id)}
                        >
                          {activatingItemId === item.id
                            ? "در حال فعال‌سازی…"
                            : "فعال‌سازی مداخله"}
                        </Button>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          <div className="prescription-history">
            <div className="section-heading">
              <div>
                <span className="eyebrow">رد تصمیم نسخه</span>
                <h3>تاریخچه نسخه‌ها</h3>
              </div>
              <Badge tone="neutral">
                {prescriptions.length.toLocaleString("fa-IR")} نسخه
              </Badge>
            </div>
            <div className="prescription-history__list">
              {prescriptions.map((entry) => {
                const decision = entry.human_decisions[0] ?? null;
                const proposal = entry.accepted_payload ?? entry.machine_proposal;
                return (
                  <article className="prescription-history-card" key={entry.id}>
                    <div className="prescription-history-card__top">
                      <Badge tone={statusTone(entry.status)}>
                        {statusLabels[entry.status]}
                      </Badge>
                      <span>
                        {persianDateTime.format(new Date(entry.created_at))}
                      </span>
                    </div>
                    <strong>{proposal.summary}</strong>
                    <span>
                      {proposal.items.length.toLocaleString("fa-IR")} مداخله •{" "}
                      {entry.model_alias}
                    </span>
                    {decision ? (
                      <div>
                        <b>
                          {actionLabels[
                            decision.action as ReviewAction
                          ] ?? decision.action}
                        </b>
                        {decision.reason_text ? <p>{decision.reason_text}</p> : null}
                      </div>
                    ) : (
                      <span>هنوز تصمیم انسانی ثبت نشده است.</span>
                    )}
                  </article>
                );
              })}
            </div>
          </div>
        </>
      ) : null}
    </Panel>
  );
}
