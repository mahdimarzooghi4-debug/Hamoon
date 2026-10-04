import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { ApiError } from "../api/client";
import type { Intervention } from "../api/prescriptions";
import {
  createReferral,
  getLatestProviderMatch,
  getLatestReferral,
  getProviderMatchContext,
  getReferralEvents,
  listHouseholdInterventions,
  runProviderMatch,
  sendReferral,
  type CapacityStatus,
  type ProviderMatch,
  type ProviderMatchCandidate,
  type ProviderMatchContext,
  type Referral,
  type ReferralEvent,
  type ReferralStatus,
} from "../api/providerReferral";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
} from "../design-system/components";

type FlowState =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "error"; message: string }
  | {
      kind: "ready";
      interventions: Intervention[];
      context: ProviderMatchContext | null;
      match: ProviderMatch | null;
      referral: Referral | null;
      events: ReferralEvent[];
    };

const interventionLabels: Record<string, string> = {
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

const variableLabels: Record<string, string> = {
  P: "مشارکت",
  G: "ظرفیت رشد",
  O: "فرصت",
  R: "تاب‌آوری",
};

const capacityLabels: Record<CapacityStatus, string> = {
  AVAILABLE: "ظرفیت موجود",
  FULL: "ظرفیت تکمیل",
  UNAVAILABLE: "غیرفعال",
  UNKNOWN: "ظرفیت نامشخص",
};

const referralLabels: Record<ReferralStatus, string> = {
  READY: "آماده ارسال",
  SENT: "ارسال شده",
  ACCEPTED: "پذیرفته شده",
  WAITING_CAPACITY: "در انتظار ظرفیت",
  NEEDS_INFORMATION: "نیازمند اطلاعات",
  IN_PROGRESS: "در حال اجرا",
  COMPLETED: "تکمیل شده",
  REJECTED: "رد شده",
  NO_RESPONSE: "بدون پاسخ",
  CANCELLED: "لغو شده",
};

const reasonLabels: Record<string, string> = {
  INTERVENTION_TYPE_NOT_SUPPORTED: "نوع مداخله پشتیبانی نمی‌شود",
  COVERAGE_POLICY_CONTEXT_MISSING: "زمینه پوشش خدمت تنظیم نشده",
  COVERAGE_CONTEXT_MISSING: "اطلاعات محدوده خدمت موجود نیست",
  OUTSIDE_SERVICE_COVERAGE: "خارج از محدوده پوشش خدمت",
  CAPACITY_UNKNOWN: "وضعیت ظرفیت نامشخص است",
  CAPACITY_FULL: "ظرفیت تکمیل است",
  CAPACITY_UNAVAILABLE: "ظرفیت در دسترس نیست",
};

const factLabels: Record<string, string> = {
  "geo.coverage_code": "محدوده جغرافیایی خدمت",
  "contact.phone": "شماره تماس",
  "contact.mobile": "شماره همراه",
  "identity.national_id": "شناسه هویتی",
  "household.member_count": "تعداد اعضای خانوار",
};

const terminalReferralStatuses = new Set<ReferralStatus>([
  "COMPLETED",
  "REJECTED",
  "NO_RESPONSE",
  "CANCELLED",
]);

const persianDateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function eligibleInterventions(items: Intervention[]): Intervention[] {
  return items.filter((item) =>
    ["ACTIVE", "READY_FOR_REFERRAL", "REFERRED"].includes(item.status),
  );
}

function referralTone(
  status: ReferralStatus,
): "accent" | "success" | "warning" | "danger" | "neutral" {
  if (status === "COMPLETED" || status === "ACCEPTED" || status === "IN_PROGRESS") {
    return "success";
  }
  if (status === "REJECTED" || status === "CANCELLED" || status === "NO_RESPONSE") {
    return "danger";
  }
  if (status === "WAITING_CAPACITY" || status === "NEEDS_INFORMATION") {
    return "warning";
  }
  return "accent";
}

function capacityTone(
  status: CapacityStatus,
): "success" | "warning" | "danger" | "neutral" {
  if (status === "AVAILABLE") return "success";
  if (status === "FULL" || status === "UNAVAILABLE") return "danger";
  return "warning";
}

function reasonLabel(reason: string): string {
  return reasonLabels[reason] ?? reason.replaceAll("_", " ");
}

function factLabel(factType: string): string {
  return factLabels[factType] ?? `داده پذیرفته‌شده: ${factType}`;
}

function sendIdempotencyKey(referral: Referral): string {
  const storageKey = `hamoon.referral.send.${referral.id}.${referral.version}`;
  const existing = window.sessionStorage.getItem(storageKey);
  if (existing) return existing;
  const value = `hamoon-send-${crypto.randomUUID()}`;
  window.sessionStorage.setItem(storageKey, value);
  return value;
}

export function ProviderReferralSection({
  householdId,
}: {
  householdId: string;
}) {
  const [state, setState] = useState<FlowState>({ kind: "loading" });
  const [selectedInterventionId, setSelectedInterventionId] = useState("");
  const [serviceType, setServiceType] = useState("");
  const [selectedCandidateKey, setSelectedCandidateKey] = useState("");
  const [priority, setPriority] = useState("NORMAL");
  const [responseDueAt, setResponseDueAt] = useState("");
  const [sharedFactIds, setSharedFactIds] = useState<Set<string>>(new Set());
  const [matching, setMatching] = useState(false);
  const [creating, setCreating] = useState(false);
  const [sending, setSending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadForIntervention = useCallback(
    async (interventions: Intervention[], interventionId: string) => {
      if (!interventionId) {
        setState({
          kind: "ready",
          interventions,
          context: null,
          match: null,
          referral: null,
          events: [],
        });
        return;
      }

      try {
        const [context, match, referral] = await Promise.all([
          getProviderMatchContext(interventionId),
          getLatestProviderMatch(interventionId),
          getLatestReferral(interventionId),
        ]);
        const events =
          referral === null ? [] : await getReferralEvents(referral.id);
        setState({
          kind: "ready",
          interventions,
          context,
          match,
          referral,
          events,
        });
        setServiceType((current) => {
          if (context.service_types.some((item) => item.service_type === current)) {
            return current;
          }
          return context.service_types[0]?.service_type ?? "";
        });
      } catch (error: unknown) {
        if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
          setState({ kind: "auth-required" });
        } else {
          setState({
            kind: "error",
            message: "اطلاعات تطبیق ارائه‌دهنده و ارجاع دریافت نشد.",
          });
        }
      }
    },
    [],
  );

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    setActionError(null);
    try {
      const all = await listHouseholdInterventions(householdId);
      const interventions = eligibleInterventions(all);
      const selected =
        interventions.find((item) => item.id === selectedInterventionId)?.id ??
        interventions[0]?.id ??
        "";
      setSelectedInterventionId(selected);
      await loadForIntervention(interventions, selected);
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
        setState({ kind: "auth-required" });
      } else {
        setState({
          kind: "error",
          message: "مداخلات پرونده دریافت نشدند.",
        });
      }
    }
  }, [householdId, loadForIntervention, selectedInterventionId]);

  useEffect(() => {
    void load();
  }, [householdId]);

  const ready = state.kind === "ready" ? state : null;
  const context = ready?.context ?? null;
  const match = ready?.match ?? null;
  const referral = ready?.referral ?? null;
  const events = ready?.events ?? [];
  const selectedIntervention =
    ready?.interventions.find((item) => item.id === selectedInterventionId) ?? null;

  const matchIsCurrent =
    context !== null &&
    match !== null &&
    match.household_context_version === context.household_context_version &&
    match.service_type === serviceType;

  const eligibleCandidates = useMemo(
    () =>
      match?.candidates.filter((candidate) => candidate.eligibility === "ELIGIBLE") ??
      [],
    [match],
  );

  const selectedCandidate = useMemo(() => {
    if (!match) return null;
    return (
      match.candidates.find(
        (candidate) =>
          `${candidate.provider_id}:${candidate.provider_service_id}` ===
          selectedCandidateKey,
      ) ?? null
    );
  }, [match, selectedCandidateKey]);

  const canCreateNewReferral =
    referral === null || terminalReferralStatuses.has(referral.status);

  async function selectIntervention(interventionId: string) {
    if (ready === null) return;
    setSelectedInterventionId(interventionId);
    setSelectedCandidateKey("");
    setSharedFactIds(new Set());
    setActionError(null);
    setState({ kind: "loading" });
    await loadForIntervention(ready.interventions, interventionId);
  }

  async function runMatch() {
    if (context === null || serviceType.length === 0) return;
    setMatching(true);
    setActionError(null);
    try {
      const nextMatch = await runProviderMatch(
        context.intervention_id,
        serviceType,
        context.household_context_version,
      );
      setState((current) =>
        current.kind === "ready" ? { ...current, match: nextMatch } : current,
      );
      const firstEligible = nextMatch.candidates.find(
        (candidate) => candidate.eligibility === "ELIGIBLE",
      );
      setSelectedCandidateKey(
        firstEligible
          ? `${firstEligible.provider_id}:${firstEligible.provider_service_id}`
          : "",
      );
    } catch (error: unknown) {
      if (
        error instanceof ApiError &&
        error.code === "HOUSEHOLD_CONTEXT_VERSION_CONFLICT"
      ) {
        setActionError(
          "اطلاعات پذیرفته‌شده خانوار تغییر کرده است. context تازه بارگذاری شد؛ تطبیق را دوباره اجرا کنید.",
        );
        if (ready) {
          await loadForIntervention(ready.interventions, context.intervention_id);
        }
      } else if (error instanceof ApiError && error.code === "ACCEPTED_STATE_REQUIRED") {
        setActionError("برای تطبیق ارائه‌دهنده باید Accepted State معتبر وجود داشته باشد.");
      } else {
        setActionError("تطبیق ارائه‌دهنده انجام نشد.");
      }
    } finally {
      setMatching(false);
    }
  }

  function toggleFact(factId: string) {
    setSharedFactIds((current) => {
      const next = new Set(current);
      if (next.has(factId)) next.delete(factId);
      else next.add(factId);
      return next;
    });
  }

  async function createSelectedReferral() {
    if (
      context === null ||
      selectedCandidate === null ||
      selectedCandidate.eligibility !== "ELIGIBLE" ||
      !matchIsCurrent
    ) {
      return;
    }
    setCreating(true);
    setActionError(null);
    try {
      const created = await createReferral(context.intervention_id, {
        providerId: selectedCandidate.provider_id,
        providerServiceId: selectedCandidate.provider_service_id,
        priority,
        responseDueAt:
          responseDueAt.trim().length === 0
            ? null
            : new Date(responseDueAt).toISOString(),
        sharedFacts: context.shareable_facts
          .filter((fact) => sharedFactIds.has(fact.fact_id))
          .map((fact) => ({
            sourceFactId: fact.fact_id,
            purpose: "SERVICE_DELIVERY",
          })),
      });
      setState((current) =>
        current.kind === "ready"
          ? { ...current, referral: created, events: [] }
          : current,
      );
    } catch (error: unknown) {
      if (
        error instanceof ApiError &&
        error.code === "PROVIDER_NOT_ELIGIBLE_IN_LATEST_MATCH"
      ) {
        setActionError(
          "این گزینه دیگر در آخرین تطبیق واجد شرایط نیست. تطبیق را دوباره اجرا کنید.",
        );
      } else if (error instanceof ApiError && error.status === 422) {
        setActionError(
          "ارجاع با داده‌های انتخاب‌شده قابل ایجاد نیست. گزینه ارائه‌دهنده و داده‌های اشتراکی را بررسی کنید.",
        );
      } else {
        setActionError("ایجاد ارجاع انجام نشد.");
      }
    } finally {
      setCreating(false);
    }
  }

  async function sendReadyReferral() {
    if (referral === null || referral.status !== "READY") return;
    setSending(true);
    setActionError(null);
    try {
      await sendReferral(referral, sendIdempotencyKey(referral));
      if (ready) {
        await loadForIntervention(ready.interventions, referral.intervention_id);
      }
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        setActionError(
          "ارجاع هم‌زمان تغییر کرده یا کلید ارسال با درخواست دیگری استفاده شده است. وضعیت تازه بارگذاری شد.",
        );
        if (ready) {
          await loadForIntervention(ready.interventions, referral.intervention_id);
        }
      } else {
        setActionError("ارسال ارجاع انجام نشد.");
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <Panel className="provider-referral-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">قواعد تطبیق، انتخاب نهایی با انسان</span>
          <h2>تطبیق ارائه‌دهنده و ارجاع</h2>
        </div>
        {referral ? (
          <Badge tone={referralTone(referral.status)}>
            {referralLabels[referral.status]}
          </Badge>
        ) : null}
      </div>

      {actionError ? (
        <div className="inline-alert" role="alert">{actionError}</div>
      ) : null}

      {state.kind === "loading" ? (
        <LoadingState label="در حال دریافت وضعیت ارجاع…" />
      ) : null}

      {state.kind === "auth-required" ? (
        <EmptyState
          title="ورود سازمانی لازم است"
          description="تطبیق ارائه‌دهنده بدون احراز هویت اجرا نمی‌شود."
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

      {ready && ready.interventions.length === 0 ? (
        <EmptyState
          title="مداخله فعالی برای ارجاع وجود ندارد"
          description="پس از تأیید نسخه و فعال‌سازی یک آیتم مداخله، تطبیق ارائه‌دهنده از این بخش آغاز می‌شود."
        />
      ) : null}

      {ready && ready.interventions.length > 0 && context !== null ? (
        <>
          <div className="provider-match-context">
            <label>
              <span>مداخله</span>
              <select
                onChange={(event) => void selectIntervention(event.target.value)}
                value={selectedInterventionId}
              >
                {ready.interventions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {interventionLabels[item.intervention_type] ?? item.intervention_type}
                    {" — "}
                    هدف {variableLabels[item.target_pgor_variable] ?? item.target_pgor_variable}
                  </option>
                ))}
              </select>
            </label>

            <div>
              <span>نسخه اطلاعات پذیرفته‌شده</span>
              <strong>
                {context.household_context_version.toLocaleString("fa-IR")}
              </strong>
            </div>

            <div>
              <span>وضعیت مداخله</span>
              <strong>{selectedIntervention?.status ?? "—"}</strong>
            </div>
          </div>

          {context.household_context_version < 1 ? (
            <EmptyState
              title="Accepted State برای تطبیق آماده نیست"
              description="حداقل یک داده پذیرفته‌شده باید در پرونده وجود داشته باشد."
            />
          ) : context.service_types.length === 0 ? (
            <EmptyState
              title="خدمت سازگاری در رجیستری فعال نیست"
              description="برای نوع این مداخله هیچ Provider Service فعال و سازگاری ثبت نشده است."
            />
          ) : (
            <div className="provider-match-controls">
              <label>
                <span>خدمت مورد نیاز</span>
                <select
                  onChange={(event) => {
                    setServiceType(event.target.value);
                    setSelectedCandidateKey("");
                  }}
                  value={serviceType}
                >
                  {context.service_types.map((item) => (
                    <option key={item.service_type} value={item.service_type}>
                      {item.service_titles.join(" / ")}
                    </option>
                  ))}
                </select>
              </label>
              <Button disabled={matching} onClick={() => void runMatch()}>
                {matching
                  ? "در حال تطبیق…"
                  : matchIsCurrent
                    ? "تطبیق دوباره"
                    : "اجرای تطبیق"}
              </Button>
              <span>
                سامانه فقط واجدشرایط‌بودن و ظرفیت را بررسی می‌کند؛ انتخاب نهایی با مددکار است.
              </span>
            </div>
          )}

          {match !== null ? (
            <div className="provider-match-results">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">نتیجه آخرین تطبیق</span>
                  <h3>ارائه‌دهندگان بررسی‌شده</h3>
                </div>
                <div className="provider-match-counts">
                  <Badge tone="success">
                    {eligibleCandidates.length.toLocaleString("fa-IR")} واجد شرایط
                  </Badge>
                  {!matchIsCurrent ? (
                    <Badge tone="warning">نیازمند تطبیق مجدد</Badge>
                  ) : null}
                </div>
              </div>

              <div className="provider-candidates">
                {[...match.candidates]
                  .sort((a, b) =>
                    a.eligibility === b.eligibility
                      ? 0
                      : a.eligibility === "ELIGIBLE"
                        ? -1
                        : 1,
                  )
                  .map((candidate) => {
                    const key = `${candidate.provider_id}:${candidate.provider_service_id}`;
                    const selectable =
                      candidate.eligibility === "ELIGIBLE" &&
                      matchIsCurrent &&
                      canCreateNewReferral;
                    return (
                      <label
                        className={
                          selectedCandidateKey === key
                            ? "provider-candidate is-selected"
                            : "provider-candidate"
                        }
                        key={key}
                      >
                        <input
                          checked={selectedCandidateKey === key}
                          disabled={!selectable}
                          name="provider-candidate"
                          onChange={() => setSelectedCandidateKey(key)}
                          type="radio"
                        />
                        <div className="provider-candidate__main">
                          <div>
                            <strong>{candidate.provider_name}</strong>
                            <span>{candidate.service_title}</span>
                          </div>
                          <div className="provider-candidate__badges">
                            <Badge
                              tone={
                                candidate.eligibility === "ELIGIBLE"
                                  ? "success"
                                  : "danger"
                              }
                            >
                              {candidate.eligibility === "ELIGIBLE"
                                ? "واجد شرایط"
                                : "غیروجد شرایط"}
                            </Badge>
                            <Badge tone={capacityTone(candidate.capacity_status)}>
                              {capacityLabels[candidate.capacity_status]}
                            </Badge>
                          </div>
                        </div>
                        {candidate.reasons.length > 0 ? (
                          <div className="provider-candidate__reasons">
                            {candidate.reasons.map((reason) => (
                              <span key={reason}>{reasonLabel(reason)}</span>
                            ))}
                          </div>
                        ) : (
                          <span className="provider-candidate__ok">
                            نوع مداخله، قواعد شرایط و ظرفیت با وضعیت فعلی سازگارند.
                          </span>
                        )}
                      </label>
                    );
                  })}
              </div>
            </div>
          ) : null}

          {canCreateNewReferral &&
          selectedCandidate !== null &&
          matchIsCurrent ? (
            <div className="referral-builder">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">انتخاب انسانی</span>
                  <h3>ایجاد ارجاع</h3>
                </div>
                <Badge tone="accent">{selectedCandidate.provider_name}</Badge>
              </div>

              <div className="referral-builder__grid">
                <label>
                  <span>اولویت ارجاع</span>
                  <select
                    onChange={(event) => setPriority(event.target.value)}
                    value={priority}
                  >
                    <option value="NORMAL">عادی</option>
                    <option value="URGENT">فوری</option>
                  </select>
                </label>
                <label>
                  <span>مهلت پاسخ (اختیاری)</span>
                  <input
                    onChange={(event) => setResponseDueAt(event.target.value)}
                    type="datetime-local"
                    value={responseDueAt}
                  />
                </label>
              </div>

              <div className="shared-facts">
                <div>
                  <strong>اطلاعات ارسالی</strong>
                  <span>
                    فقط داده‌هایی که صریحاً انتخاب شوند هنگام ارسال به ارائه‌دهنده مشترک می‌شوند.
                  </span>
                </div>
                {context.shareable_facts.length === 0 ? (
                  <span className="shared-facts__none">
                    داده پذیرفته‌شده‌ای برای اشتراک انتخابی وجود ندارد.
                  </span>
                ) : (
                  <div className="shared-facts__list">
                    {context.shareable_facts.map((fact) => (
                      <label key={fact.fact_id}>
                        <input
                          checked={sharedFactIds.has(fact.fact_id)}
                          onChange={() => toggleFact(fact.fact_id)}
                          type="checkbox"
                        />
                        <span>{factLabel(fact.fact_type)}</span>
                        <small>
                          نسخه {fact.projection_version.toLocaleString("fa-IR")}
                        </small>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              <Button
                disabled={creating}
                onClick={() => void createSelectedReferral()}
              >
                {creating ? "در حال ایجاد ارجاع…" : "ادامه و بررسی ارجاع"}
              </Button>
            </div>
          ) : null}

          {referral !== null ? (
            <div className="referral-status">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">
                    {referral.status === "READY"
                      ? "بازبینی پیش از ارسال"
                      : "ارجاع فعال"}
                  </span>
                  <h3>{referral.provider_name}</h3>
                </div>
                <Badge tone={referralTone(referral.status)}>
                  {referralLabels[referral.status]}
                </Badge>
              </div>

              <div className="referral-summary-grid">
                <div>
                  <span>خدمت</span>
                  <strong>{referral.service_title}</strong>
                </div>
                <div>
                  <span>اولویت</span>
                  <strong>
                    {referral.priority === "URGENT" ? "فوری" : "عادی"}
                  </strong>
                </div>
                <div>
                  <span>مهلت پاسخ</span>
                  <strong>
                    {referral.response_due_at
                      ? persianDateTime.format(new Date(referral.response_due_at))
                      : "تعیین نشده"}
                  </strong>
                </div>
                <div>
                  <span>نسخه ارجاع</span>
                  <strong>{referral.version.toLocaleString("fa-IR")}</strong>
                </div>
              </div>

              <div className="referral-shared-summary">
                <strong>داده‌های انتخاب‌شده برای اشتراک</strong>
                {referral.data_items.length === 0 ? (
                  <span>هیچ داده پرونده‌ای برای اشتراک انتخاب نشده است.</span>
                ) : (
                  <div>
                    {referral.data_items.map((item) => (
                      <Badge key={item.id} tone="neutral">
                        {factLabel(item.data_category)}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {referral.status === "READY" ? (
                <div className="referral-send-box">
                  <p>
                    انتخاب ارائه‌دهنده یک تصمیم انسانی ثبت‌شده است. ارسال فقط همین
                    داده‌های انتخاب‌شده را به payload مجاز اضافه می‌کند.
                  </p>
                  <Button disabled={sending} onClick={() => void sendReadyReferral()}>
                    {sending ? "در حال ارسال…" : "تأیید و ارسال ارجاع"}
                  </Button>
                </div>
              ) : (
                <div className="referral-live">
                  <div className="referral-live__header">
                    <strong>تاریخچه وضعیت</strong>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        ready
                          ? void loadForIntervention(
                              ready.interventions,
                              referral.intervention_id,
                            )
                          : undefined
                      }
                    >
                      تازه‌سازی
                    </Button>
                  </div>
                  {referral.external_referral_id ? (
                    <span className="ltr-value">
                      شناسه بیرونی: {referral.external_referral_id}
                    </span>
                  ) : null}
                  {events.length === 0 ? (
                    <span>رویداد وضعیت دیگری ثبت نشده است.</span>
                  ) : (
                    <div className="referral-timeline">
                      {events.map((event) => (
                        <article key={event.id}>
                          <span className="referral-timeline__dot" />
                          <div>
                            <strong>
                              {referralLabels[event.to_status] ?? event.to_status}
                            </strong>
                            <span>
                              {persianDateTime.format(new Date(event.occurred_at))}
                              {" • "}
                              {event.source}
                            </span>
                            {event.reason_code ? (
                              <small>{reasonLabel(event.reason_code)}</small>
                            ) : null}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {terminalReferralStatuses.has(referral.status) ? (
                <div className="referral-terminal-note">
                  این ارجاع بسته شده است. برای انتخاب ارائه‌دهنده دیگر، تطبیق تازه اجرا
                  و ارجاع جدید ایجاد کنید؛ تاریخچه قبلی بازنویسی نمی‌شود.
                </div>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </Panel>
  );
}
