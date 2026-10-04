import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import { ApiError } from "../api/client";
import {
  generateDiagnosis,
  listDiagnoses,
  reviewDiagnosis,
  type DiagnosisCategory,
  type DiagnosisHistoryEntry,
  type DiagnosisItem,
  type DiagnosisProposal,
  type DiagnosisStatus,
  type DiagnosisUncertainty,
  type HumanDecisionAction,
} from "../api/diagnosis";
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
  | { kind: "ready"; entries: DiagnosisHistoryEntry[] };

type ReviewMode = HumanDecisionAction | null;

interface DraftItem {
  code: string;
  category: DiagnosisCategory;
  title: string;
  rationale: string;
  supportingRefs: string;
  uncertainty: DiagnosisUncertainty;
}

interface DraftProposal {
  summary: string;
  items: DraftItem[];
  reviewFlags: string;
}

const statusLabels: Record<DiagnosisStatus, string> = {
  UNDER_REVIEW: "نیازمند تصمیم مددکار",
  CONFIRMED: "تأییدشده",
  MODIFIED: "اصلاح‌شده",
  REPLACED: "جایگزین‌شده",
  REJECTED: "ردشده",
  DEFERRED: "به تعویق افتاده",
};

const actionLabels: Record<HumanDecisionAction, string> = {
  CONFIRM: "تأیید بدون تغییر",
  MODIFY: "اصلاح تشخیص",
  REPLACE: "جایگزینی تشخیص",
  REJECT: "رد تشخیص",
  DEFER: "بررسی در زمان دیگر",
};

const categoryLabels: Record<DiagnosisCategory, string> = {
  NEED: "نیاز",
  RISK: "ریسک",
  CAPACITY: "ظرفیت",
  CONSTRAINT: "محدودیت",
};

const uncertaintyLabels: Record<DiagnosisUncertainty, string> = {
  LOW: "عدم‌قطعیت کم",
  MEDIUM: "عدم‌قطعیت متوسط",
  HIGH: "عدم‌قطعیت زیاد",
  UNKNOWN: "عدم‌قطعیت نامشخص",
};

const defaultReasonCodes: Record<HumanDecisionAction, string> = {
  CONFIRM: "CONFIRMED_AS_IS",
  MODIFY: "PROFESSIONAL_JUDGMENT",
  REPLACE: "REPLACEMENT_REQUIRED",
  REJECT: "INSUFFICIENT_SUPPORT",
  DEFER: "MORE_EVIDENCE_REQUIRED",
};

const persianDateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function statusTone(
  status: DiagnosisStatus,
): "accent" | "success" | "warning" | "danger" | "neutral" {
  if (status === "CONFIRMED" || status === "MODIFIED" || status === "REPLACED") {
    return "success";
  }
  if (status === "REJECTED") return "danger";
  if (status === "DEFERRED") return "warning";
  return "accent";
}

function canReview(status: DiagnosisStatus): boolean {
  return status === "UNDER_REVIEW" || status === "DEFERRED";
}

function proposalToDraft(proposal: DiagnosisProposal): DraftProposal {
  return {
    summary: proposal.summary,
    items: proposal.items.map((item) => ({
      code: item.code,
      category: item.category,
      title: item.title,
      rationale: item.rationale,
      supportingRefs: item.supporting_feature_refs.join(", "),
      uncertainty: item.uncertainty,
    })),
    reviewFlags: proposal.review_flags.join(", "),
  };
}

function draftToProposal(draft: DraftProposal): DiagnosisProposal {
  return {
    schema_version: "diagnosis-v1",
    summary: draft.summary.trim(),
    items: draft.items.map((item) => ({
      code: item.code.trim(),
      category: item.category,
      title: item.title.trim(),
      rationale: item.rationale.trim(),
      supporting_feature_refs: item.supportingRefs
        .split(",")
        .map((value) => value.trim())
        .filter((value, index, all) => value.length > 0 && all.indexOf(value) === index),
      uncertainty: item.uncertainty,
    })),
    review_flags: draft.reviewFlags
      .split(",")
      .map((value) => value.trim())
      .filter((value, index, all) => value.length > 0 && all.indexOf(value) === index),
  };
}

function isDraftValid(draft: DraftProposal): boolean {
  return (
    draft.summary.trim().length > 0 &&
    draft.items.every(
      (item) =>
        item.code.trim().length > 0 &&
        item.title.trim().length > 0 &&
        item.rationale.trim().length > 0,
    )
  );
}

export function DiagnosisSection({
  householdId,
  pgorSnapshotId,
}: {
  householdId: string;
  pgorSnapshotId: string | null;
}) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [reviewMode, setReviewMode] = useState<ReviewMode>(null);
  const [reasonCode, setReasonCode] = useState("");
  const [reasonText, setReasonText] = useState("");
  const [draft, setDraft] = useState<DraftProposal | null>(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const entries = await listDiagnoses(householdId);
      setState({ kind: "ready", entries });
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
        setState({ kind: "auth-required" });
      } else {
        setState({
          kind: "error",
          message: "تاریخچه تشخیص دریافت نشد.",
        });
      }
    }
  }, [householdId]);

  useEffect(() => {
    void load();
  }, [load]);

  const entries = state.kind === "ready" ? state.entries : [];
  const latest = entries[0] ?? null;

  const finalProposal = useMemo(() => {
    if (latest === null) return null;
    return latest.accepted_payload ?? latest.machine_proposal;
  }, [latest]);

  function openReview(action: HumanDecisionAction) {
    if (latest === null) return;
    setActionError(null);
    setReviewMode(action);
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
    setReviewMode(null);
    setDraft(null);
    setReasonText("");
    setReasonCode("");
    setActionError(null);
  }

  async function handleGenerate() {
    if (pgorSnapshotId === null) return;
    setGenerating(true);
    setActionError(null);
    try {
      await generateDiagnosis(householdId, pgorSnapshotId);
      await load();
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        setActionError(
          error.code === "AI_PROVIDER_UNAVAILABLE"
            ? "سرویس تشخیص هوشمند در دسترس نیست."
            : error.code === "AI_ROUTING_POLICY_NOT_FOUND"
              ? "مسیر فعال تشخیص هوشمند تنظیم نشده است."
              : "ساخت پیشنهاد تشخیص انجام نشد.",
        );
      } else {
        setActionError("ساخت پیشنهاد تشخیص انجام نشد.");
      }
    } finally {
      setGenerating(false);
    }
  }

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (latest === null || reviewMode === null) return;

    const needsStructuredPayload =
      reviewMode === "MODIFY" || reviewMode === "REPLACE";

    if (needsStructuredPayload && (draft === null || !isDraftValid(draft))) {
      setActionError("خلاصه، کد، عنوان و استدلال همه موارد تشخیص باید تکمیل شوند.");
      return;
    }

    if (
      reviewMode !== "CONFIRM" &&
      reasonText.trim().length === 0
    ) {
      setActionError("برای این تصمیم، توضیح حرفه‌ای مددکار الزامی است.");
      return;
    }

    setSaving(true);
    setActionError(null);
    try {
      await reviewDiagnosis(latest, reviewMode, {
        reasonCode: reasonCode.trim() || null,
        reasonText: reasonText.trim() || null,
        modifiedPayload:
          needsStructuredPayload && draft !== null
            ? draftToProposal(draft)
            : undefined,
      });
      closeReview();
      await load();
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        setActionError(
          "این تشخیص هم‌زمان تغییر کرده است. نسخه تازه بارگذاری شد؛ تصمیم را دوباره بررسی کنید.",
        );
        await load();
      } else if (error instanceof ApiError && error.status === 422) {
        setActionError(
          "ساختار تصمیم با قرارداد تشخیص معتبر نیست. ورودی‌ها را بررسی کنید.",
        );
      } else {
        setActionError("ثبت تصمیم مددکار انجام نشد.");
      }
    } finally {
      setSaving(false);
    }
  }

  function updateDraftItem(index: number, patch: Partial<DraftItem>) {
    setDraft((current) => {
      if (current === null) return current;
      return {
        ...current,
        items: current.items.map((item, itemIndex) =>
          itemIndex === index ? { ...item, ...patch } : item,
        ),
      };
    });
  }

  function addDraftItem() {
    setDraft((current) => {
      if (current === null) return current;
      return {
        ...current,
        items: [
          ...current.items,
          {
            code: "",
            category: "NEED",
            title: "",
            rationale: "",
            supportingRefs: "",
            uncertainty: "UNKNOWN",
          },
        ],
      };
    });
  }

  function removeDraftItem(index: number) {
    setDraft((current) => {
      if (current === null) return current;
      return {
        ...current,
        items: current.items.filter((_, itemIndex) => itemIndex !== index),
      };
    });
  }

  return (
    <Panel className="diagnosis-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">پیشنهاد ماشین، تصمیم انسان</span>
          <h2>تشخیص هامون</h2>
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

      {state.kind === "loading" ? <LoadingState label="در حال دریافت تشخیص…" /> : null}

      {state.kind === "auth-required" ? (
        <EmptyState
          title="ورود سازمانی لازم است"
          description="تشخیص بدون احراز هویت از API خوانده نمی‌شود."
        />
      ) : null}

      {state.kind === "error" ? (
        <ErrorState
          description={state.message}
          action={<Button variant="secondary" onClick={() => void load()}>تلاش دوباره</Button>}
        />
      ) : null}

      {state.kind === "ready" && latest === null ? (
        <div className="diagnosis-empty">
          <EmptyState
            title="هنوز تشخیص هوشمندی ثبت نشده است"
            description={
              pgorSnapshotId === null
                ? "ابتدا باید PGOR رسمی برای پرونده وجود داشته باشد."
                : "پیشنهاد تشخیص فقط از snapshot رسمی PGOR و feature package معتبر ساخته می‌شود."
            }
          />
          {pgorSnapshotId !== null ? (
            <Button disabled={generating} onClick={() => void handleGenerate()}>
              {generating ? "در حال ساخت پیشنهاد…" : "ساخت پیشنهاد تشخیص"}
            </Button>
          ) : null}
        </div>
      ) : null}

      {state.kind === "ready" && latest !== null && finalProposal !== null ? (
        <>
          <div className="diagnosis-current">
            <div className="diagnosis-summary">
              <div className="diagnosis-summary__meta">
                <Badge tone="accent">پیشنهاد تحلیلی هامون</Badge>
                <span>{persianDateTime.format(new Date(latest.generated_at))}</span>
                <span>{latest.model_alias}</span>
              </div>
              <h3>{latest.machine_proposal.summary}</h3>
              {latest.accepted_payload !== null &&
              latest.accepted_payload.summary !== latest.machine_proposal.summary ? (
                <div className="diagnosis-final-summary">
                  <span>تشخیص نهایی پس از تصمیم مددکار</span>
                  <strong>{latest.accepted_payload.summary}</strong>
                </div>
              ) : null}
            </div>

            <div className="diagnosis-items">
              {finalProposal.items.length === 0 ? (
                <EmptyState
                  title="مورد تشخیصی ساختاریافته‌ای وجود ندارد"
                  description="خلاصه تشخیص ثبت شده، اما آرایه items خالی است."
                />
              ) : (
                finalProposal.items.map((item) => (
                  <article className="diagnosis-item" key={`${item.code}-${item.title}`}>
                    <div className="diagnosis-item__top">
                      <Badge tone="accent">{categoryLabels[item.category]}</Badge>
                      <Badge tone={item.uncertainty === "HIGH" ? "warning" : "neutral"}>
                        {uncertaintyLabels[item.uncertainty]}
                      </Badge>
                    </div>
                    <strong>{item.title}</strong>
                    <p>{item.rationale}</p>
                    {item.supporting_feature_refs.length > 0 ? (
                      <div className="diagnosis-refs">
                        {item.supporting_feature_refs.map((ref) => (
                          <span key={ref}>{ref}</span>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))
              )}
            </div>

            {latest.machine_proposal.review_flags.length > 0 ? (
              <div className="diagnosis-flags">
                <strong>موارد نیازمند توجه مددکار</strong>
                <div>
                  {latest.machine_proposal.review_flags.map((flag) => (
                    <Badge key={flag} tone="warning">{flag}</Badge>
                  ))}
                </div>
              </div>
            ) : null}

            {canReview(latest.status) ? (
              <div className="diagnosis-actions">
                <Button onClick={() => openReview("CONFIRM")}>تأیید تشخیص</Button>
                <Button variant="secondary" onClick={() => openReview("MODIFY")}>اصلاح</Button>
                <Button variant="secondary" onClick={() => openReview("REPLACE")}>جایگزینی</Button>
                <Button variant="quiet" onClick={() => openReview("DEFER")}>بررسی بعدی</Button>
                <Button variant="quiet" onClick={() => openReview("REJECT")}>رد تشخیص</Button>
              </div>
            ) : (
              <div className="diagnosis-terminal">
                <Badge tone={statusTone(latest.status)}>
                  تصمیم انسانی ثبت شده است
                </Badge>
                {latest.reviewed_at ? (
                  <span>{persianDateTime.format(new Date(latest.reviewed_at))}</span>
                ) : null}
              </div>
            )}
          </div>

          {reviewMode !== null ? (
            <form className="diagnosis-review-form" onSubmit={submitReview}>
              <div className="diagnosis-review-form__heading">
                <div>
                  <span className="eyebrow">ثبت تصمیم انسانی</span>
                  <h3>{actionLabels[reviewMode]}</h3>
                </div>
                <button className="drawer-close" onClick={closeReview} type="button" aria-label="بستن">×</button>
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
                  <span>توضیح مددکار {reviewMode === "CONFIRM" ? "(اختیاری)" : ""}</span>
                  <textarea
                    maxLength={1000}
                    onChange={(event) => setReasonText(event.target.value)}
                    rows={3}
                    value={reasonText}
                  />
                </label>
              </div>

              {(reviewMode === "MODIFY" || reviewMode === "REPLACE") && draft !== null ? (
                <div className="diagnosis-editor">
                  <label>
                    <span>خلاصه تشخیص نهایی</span>
                    <textarea
                      maxLength={2000}
                      onChange={(event) =>
                        setDraft((current) =>
                          current === null ? current : { ...current, summary: event.target.value },
                        )
                      }
                      rows={3}
                      value={draft.summary}
                    />
                  </label>

                  <div className="diagnosis-editor__items">
                    {draft.items.map((item, index) => (
                      <div className="diagnosis-editor-item" key={index}>
                        <div className="diagnosis-editor-item__top">
                          <strong>مورد {String(index + 1).replace(/[0-9]/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)])}</strong>
                          <Button type="button" variant="quiet" onClick={() => removeDraftItem(index)}>
                            حذف مورد
                          </Button>
                        </div>
                        <div className="form-grid">
                          <label>
                            <span>کد</span>
                            <input
                              maxLength={150}
                              onChange={(event) => updateDraftItem(index, { code: event.target.value })}
                              value={item.code}
                            />
                          </label>
                          <label>
                            <span>دسته</span>
                            <select
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  category: event.target.value as DiagnosisCategory,
                                })
                              }
                              value={item.category}
                            >
                              {Object.entries(categoryLabels).map(([value, label]) => (
                                <option key={value} value={value}>{label}</option>
                              ))}
                            </select>
                          </label>
                          <label>
                            <span>عدم‌قطعیت</span>
                            <select
                              onChange={(event) =>
                                updateDraftItem(index, {
                                  uncertainty: event.target.value as DiagnosisUncertainty,
                                })
                              }
                              value={item.uncertainty}
                            >
                              {Object.entries(uncertaintyLabels).map(([value, label]) => (
                                <option key={value} value={value}>{label}</option>
                              ))}
                            </select>
                          </label>
                          <label className="form-grid__wide">
                            <span>عنوان</span>
                            <input
                              maxLength={300}
                              onChange={(event) => updateDraftItem(index, { title: event.target.value })}
                              value={item.title}
                            />
                          </label>
                          <label className="form-grid__wide">
                            <span>استدلال</span>
                            <textarea
                              maxLength={2000}
                              onChange={(event) => updateDraftItem(index, { rationale: event.target.value })}
                              rows={3}
                              value={item.rationale}
                            />
                          </label>
                          <label className="form-grid__wide">
                            <span>ارجاع‌های پشتیبان، جداشده با ویرگول</span>
                            <input
                              onChange={(event) =>
                                updateDraftItem(index, { supportingRefs: event.target.value })
                              }
                              value={item.supportingRefs}
                            />
                          </label>
                        </div>
                      </div>
                    ))}
                  </div>

                  <Button type="button" variant="secondary" onClick={addDraftItem}>
                    افزودن مورد تشخیصی
                  </Button>

                  <label>
                    <span>پرچم‌های بازبینی، جداشده با ویرگول</span>
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
              ) : null}

              <div className="diagnosis-review-form__actions">
                <Button disabled={saving} type="submit">
                  {saving ? "در حال ثبت…" : "ثبت تصمیم"}
                </Button>
                <Button disabled={saving} type="button" variant="secondary" onClick={closeReview}>
                  انصراف
                </Button>
              </div>
            </form>
          ) : null}

          <div className="diagnosis-history">
            <div className="section-heading">
              <div>
                <span className="eyebrow">رد تصمیم و یادگیری</span>
                <h3>تاریخچه تشخیص</h3>
              </div>
              <Badge tone="neutral">{entries.length.toLocaleString("fa-IR")} تشخیص</Badge>
            </div>

            <div className="diagnosis-history__list">
              {entries.map((entry) => {
                const latestDecision = entry.human_decisions[0] ?? null;
                const displayed = entry.accepted_payload ?? entry.machine_proposal;
                return (
                  <article className="diagnosis-history-card" key={entry.id}>
                    <div className="diagnosis-history-card__top">
                      <Badge tone={statusTone(entry.status)}>{statusLabels[entry.status]}</Badge>
                      <span>{persianDateTime.format(new Date(entry.created_at))}</span>
                    </div>
                    <strong>{displayed.summary}</strong>
                    <span>
                      {entry.model_alias} • نسخه {entry.version.toLocaleString("fa-IR")}
                    </span>
                    {latestDecision ? (
                      <div className="diagnosis-history-card__decision">
                        <b>{actionLabels[latestDecision.action]}</b>
                        {latestDecision.reason_text ? <p>{latestDecision.reason_text}</p> : null}
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
