import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import {
  claimWorkItem,
  getWorkQueue,
  type WorkItem,
  type WorkItemType,
} from "../api/operations";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  Panel,
} from "../design-system/components";

type QueueLoadState =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: WorkItem[] };

type Filter = "ALL" | WorkItemType;

const typeLabels: Record<WorkItemType, string> = {
  DIAGNOSIS_REVIEW: "بازبینی تشخیص",
  PRESCRIPTION_REVIEW: "بازبینی نسخه",
  REFERRAL_FOLLOWUP: "پیگیری ارجاع",
  REASSESSMENT_DUE: "بازسنجی موعددار",
  OUTCOME_REVIEW: "بازبینی نتیجه",
  DATA_COMPLETION: "تکمیل داده",
  CONFLICT_RESOLUTION: "حل تعارض",
  AI_FALLBACK: "بررسی جایگزین هوش مصنوعی",
  REASSESSMENT: "بازسنجی",
};

const persianDateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function dueLabel(value: string | null): string {
  return value === null ? "بدون موعد" : persianDateTime.format(new Date(value));
}

function isOverdue(item: WorkItem): boolean {
  return item.is_overdue;
}

function priorityTone(priority: number): "danger" | "warning" | "neutral" {
  if (priority >= 80) return "danger";
  if (priority >= 50) return "warning";
  return "neutral";
}

export function WorkQueuePage() {
  const [state, setState] = useState<QueueLoadState>({ kind: "loading" });
  const [filter, setFilter] = useState<Filter>("ALL");
  const [claimingId, setClaimingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const items = await getWorkQueue(100);
      setState({ kind: "ready", items });
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
        setState({ kind: "auth-required" });
        return;
      }
      setState({ kind: "error", message: "ارتباط با سرویس کارتابل برقرار نشد." });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const items = state.kind === "ready" ? state.items : [];
  const filtered =
    filter === "ALL" ? items : items.filter((item) => item.work_type === filter);

  const summary = useMemo(
    () => ({
      open: items.filter((item) => item.status === "OPEN").length,
      claimed: items.filter((item) => item.status === "CLAIMED").length,
      overdue: items.filter(isOverdue).length,
      total: items.length,
    }),
    [items],
  );

  async function claim(item: WorkItem) {
    setActionError(null);
    setClaimingId(item.id);
    try {
      const updated = await claimWorkItem(item);
      setState((current) =>
        current.kind === "ready"
          ? {
              kind: "ready",
              items: current.items.map((candidate) =>
                candidate.id === updated.id ? updated : candidate,
              ),
            }
          : current,
      );
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        setActionError(
          "این اقدام هم‌زمان تغییر کرده است. اطلاعات تازه بارگذاری شد؛ دوباره بررسی کنید.",
        );
        await load();
      } else {
        setActionError("در اختیار گرفتن این اقدام انجام نشد.");
      }
    } finally {
      setClaimingId(null);
    }
  }

  return (
    <div className="page-stack">
      <header className="page-heading">
        <div>
          <span className="eyebrow">صف اقدام‌های مددکار</span>
          <h1>کارتابل من</h1>
          <p>فقط اقدام‌های باز و در حال رسیدگی که سامانه برای شما برگردانده است.</p>
        </div>
        {state.kind === "ready" ? (
          <Button variant="secondary" onClick={() => void load()}>
            تازه‌سازی
          </Button>
        ) : null}
      </header>

      <section className="metric-grid">
        <MetricCard label="همه اقدام‌ها" value={state.kind === "ready" ? summary.total : "—"} />
        <MetricCard label="باز" value={state.kind === "ready" ? summary.open : "—"} />
        <MetricCard
          label="در حال رسیدگی"
          value={state.kind === "ready" ? summary.claimed : "—"}
        />
        <MetricCard label="عقب‌افتاده" value={state.kind === "ready" ? summary.overdue : "—"} />
      </section>

      <Panel>
        <div className="filter-row" role="group" aria-label="فیلتر نوع اقدام">
          {(
            [
              ["ALL", "همه"],
              ["DIAGNOSIS_REVIEW", "تشخیص"],
              ["PRESCRIPTION_REVIEW", "نسخه"],
              ["REFERRAL_FOLLOWUP", "پیگیری ارجاع"],
              ["REASSESSMENT_DUE", "بازسنجی"],
              ["OUTCOME_REVIEW", "نتیجه"],
              ["DATA_COMPLETION", "تکمیل داده"],
              ["CONFLICT_RESOLUTION", "حل تعارض"],
              ["AI_FALLBACK", "بررسی جایگزین"],
            ] as const
          ).map(([value, label]) => (
            <button
              className={filter === value ? "filter-chip is-active" : "filter-chip"}
              key={value}
              onClick={() => setFilter(value)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>

        {actionError ? (
          <div className="inline-alert" role="alert">{actionError}</div>
        ) : null}

        {state.kind === "loading" ? <LoadingState /> : null}
        {state.kind === "auth-required" ? (
          <EmptyState
            title="ورود سازمانی لازم است"
            description="توکن دسترسی موجود نیست؛ کارتابل بدون احراز هویت داده‌ای نمایش نمی‌دهد."
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
        {state.kind === "ready" && filtered.length === 0 ? (
          <EmptyState
            title="موردی در این فیلتر نیست"
            description="فیلتر دیگری انتخاب کنید یا بعداً دوباره کارتابل را بررسی کنید."
          />
        ) : null}

        {state.kind === "ready" && filtered.length > 0 ? (
          <div className="work-list">
            {filtered.map((item) => (
              <article className="work-card" key={item.id}>
                <div className="work-card__header">
                  <div className="work-card__badges">
                    <Badge tone={item.status === "CLAIMED" ? "accent" : "neutral"}>
                      {item.status === "CLAIMED" ? "در حال رسیدگی" : "باز"}
                    </Badge>
                    <Badge tone={priorityTone(item.priority)}>
                      اولویت {item.priority.toLocaleString("fa-IR")}
                    </Badge>
                    {isOverdue(item) ? <Badge tone="danger">عقب‌افتاده</Badge> : null}
                  </div>
                  <Badge tone="accent">{typeLabels[item.work_type]}</Badge>
                </div>

                <div className="work-card__body">
                  <div>
                    <h2>{item.title}</h2>
                    <p>{item.reason}</p>
                  </div>
                  <dl className="work-card__meta">
                    <div>
                      <dt>موعد</dt>
                      <dd>{dueLabel(item.due_at)}</dd>
                    </div>
                    <div>
                      <dt>نسخه</dt>
                      <dd>{item.version.toLocaleString("fa-IR")}</dd>
                    </div>
                    <div>
                      <dt>شناسه خانوار</dt>
                      <dd className="ltr-value">{item.household_id}</dd>
                    </div>
                  </dl>
                </div>

                <div className="work-card__actions">
                  {item.status === "OPEN" ? (
                    <Button
                      disabled={claimingId === item.id}
                      onClick={() => void claim(item)}
                    >
                      {claimingId === item.id ? "در حال ثبت…" : "در اختیار گرفتن"}
                    </Button>
                  ) : (
                    <Button disabled>در اختیار شماست</Button>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
