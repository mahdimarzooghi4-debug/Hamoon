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

type TypeFilter = "ALL" | WorkItemType;
type DateFilter = "TODAY" | "WEEK" | "ALL";

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

const dateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});
const dateOnly = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
});

function dueLabel(value: string | null): string {
  if (value === null) return "بدون موعد";
  const date = new Date(value);
  return dateTime.format(date);
}

function isToday(value: string | null, now = new Date()): boolean {
  if (value === null) return false;
  const due = new Date(value);
  return due.getFullYear() === now.getFullYear()
    && due.getMonth() === now.getMonth()
    && due.getDate() === now.getDate();
}

function isWithinWeek(value: string | null, now = new Date()): boolean {
  if (value === null) return false;
  const due = new Date(value);
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const end = start + 7 * 24 * 60 * 60 * 1000;
  return due.getTime() >= start && due.getTime() < end;
}

function isOverdue(item: WorkItem): boolean {
  return item.is_overdue;
}

function compareUrgency(a: WorkItem, b: WorkItem): number {
  if (a.is_overdue !== b.is_overdue) return a.is_overdue ? -1 : 1;
  if (a.priority !== b.priority) return b.priority - a.priority;
  if (a.due_at === null) return 1;
  if (b.due_at === null) return -1;
  return new Date(a.due_at).getTime() - new Date(b.due_at).getTime();
}

function WorkItemRow({
  item,
  claiming,
  onClaim,
}: {
  item: WorkItem;
  claiming: boolean;
  onClaim: (item: WorkItem) => void;
}) {
  return (
    <article className={item.is_overdue ? "queue-row is-overdue" : "queue-row"}>
      <div className="queue-row__identity">
        <strong>{item.title}</strong>
        <span className="ltr-value">{item.household_id}</span>
      </div>
      <div className="queue-row__description">
        <Badge tone="accent">{typeLabels[item.work_type]}</Badge>
        <p>{item.reason}</p>
      </div>
      <div className="queue-row__due">
        <span>{item.is_overdue ? "عقب‌افتاده" : "موعد"}</span>
        <strong>{item.due_at === null ? "بدون موعد" : dueLabel(item.due_at)}</strong>
      </div>
      <div className="queue-row__actions">
        {item.status === "OPEN" ? (
          <Button disabled={claiming} onClick={() => onClaim(item)}>
            {claiming ? "در حال ثبت…" : "در اختیار گرفتن"}
          </Button>
        ) : (
          <Badge tone="neutral">در حال رسیدگی</Badge>
        )}
      </div>
    </article>
  );
}

export function WorkQueuePage() {
  const [state, setState] = useState<QueueLoadState>({ kind: "loading" });
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("ALL");
  const [dateFilter, setDateFilter] = useState<DateFilter>("ALL");
  const [query, setQuery] = useState("");
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
  const summary = useMemo(
    () => ({
      open: items.filter((item) => item.status === "OPEN").length,
      claimed: items.filter((item) => item.status === "CLAIMED").length,
      overdue: items.filter(isOverdue).length,
      today: items.filter((item) => isToday(item.due_at)).length,
    }),
    [items],
  );

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("fa-IR");
    return items
      .filter((item) => typeFilter === "ALL" || item.work_type === typeFilter)
      .filter((item) => {
        if (dateFilter === "TODAY") return isToday(item.due_at) || item.is_overdue;
        if (dateFilter === "WEEK") return isWithinWeek(item.due_at) || item.is_overdue;
        return true;
      })
      .filter((item) => !normalized || [
        item.title,
        item.reason,
        item.household_id,
        typeLabels[item.work_type],
      ].some((value) => value.toLocaleLowerCase("fa-IR").includes(normalized)))
      .sort(compareUrgency);
  }, [dateFilter, items, query, typeFilter]);

  const openItems = filtered.filter((item) => item.status === "OPEN");
  const claimedItems = filtered.filter((item) => item.status === "CLAIMED");
  const overdueItems = items.filter(isOverdue).sort(compareUrgency);
  const upcomingItems = items
    .filter((item) => !item.is_overdue && item.due_at !== null && isWithinWeek(item.due_at))
    .sort(compareUrgency);

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
        setActionError("این اقدام هم‌زمان تغییر کرده است. اطلاعات تازه بارگذاری شد؛ دوباره بررسی کنید.");
        await load();
      } else {
        setActionError("در اختیار گرفتن این اقدام انجام نشد.");
      }
    } finally {
      setClaimingId(null);
    }
  }

  return (
    <div className="page-stack work-queue-page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">اقدام‌ها، پیگیری‌ها و تصمیم‌های ارجاع‌شده</span>
          <h1>کارتابل</h1>
          <p>اقدام‌های مجاز برای شما، بر اساس داده‌ای که سامانه برمی‌گرداند.</p>
        </div>
        {state.kind === "ready" ? (
          <Button variant="secondary" onClick={() => void load()}>تازه‌سازی</Button>
        ) : null}
      </header>

      <section className="metric-grid work-queue-metrics" aria-label="خلاصه کارتابل">
        <MetricCard label="اقدام امروز" value={state.kind === "ready" ? summary.today : "—"} />
        <MetricCard label="عقب‌افتاده" value={state.kind === "ready" ? summary.overdue : "—"} />
        <MetricCard label="نیازمند اقدام" value={state.kind === "ready" ? summary.open : "—"} />
        <MetricCard label="در حال رسیدگی" value={state.kind === "ready" ? summary.claimed : "—"} />
      </section>

      {state.kind === "loading" ? <LoadingState label="در حال دریافت کارتابل…" /> : null}
      {state.kind === "auth-required" ? (
        <EmptyState
          title="ورود سازمانی لازم است"
          description="توکن دسترسی موجود نیست؛ کارتابل بدون احراز هویت داده‌ای نمایش نمی‌دهد."
        />
      ) : null}
      {state.kind === "error" ? (
        <ErrorState
          description={state.message}
          action={<Button variant="secondary" onClick={() => void load()}>تلاش دوباره</Button>}
        />
      ) : null}

      {state.kind === "ready" ? (
        <>
          <div className="queue-toolbar">
            <div className="filter-row" role="group" aria-label="بازه موعد">
              {([
                ["TODAY", "امروز"],
                ["WEEK", "این هفته"],
                ["ALL", "همه"],
              ] as const).map(([value, label]) => (
                <button
                  className={dateFilter === value ? "filter-chip is-active" : "filter-chip"}
                  key={value}
                  onClick={() => setDateFilter(value)}
                  type="button"
                >
                  {label}
                </button>
              ))}
            </div>
            <label className="queue-search">
              <span className="sr-only">جست‌وجو در کارتابل</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="جست‌وجو در عنوان، پرونده یا توضیح"
              />
            </label>
            <label className="queue-type-filter">
              <span className="sr-only">فیلتر نوع اقدام</span>
              <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as TypeFilter)}>
                <option value="ALL">همه نوع‌ها</option>
                {Object.entries(typeLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
          </div>

          {actionError ? <div className="inline-alert" role="alert">{actionError}</div> : null}

          {filtered.length === 0 ? (
            <EmptyState
              title="موردی در این فیلتر نیست"
              description="بازه، نوع اقدام یا عبارت جست‌وجو را تغییر دهید."
            />
          ) : (
            <div className="queue-layout">
              <div className="queue-main">
                <Panel>
                  <div className="section-heading">
                    <div>
                      <h2>نیازمند اقدام</h2>
                      <p>اقدام‌های باز با ترتیب موعد و اولویت ثبت‌شده</p>
                    </div>
                    <Badge tone="accent">{openItems.length.toLocaleString("fa-IR")} مورد</Badge>
                  </div>
                  {openItems.length ? (
                    <div className="queue-list">
                      {openItems.map((item) => (
                        <WorkItemRow key={item.id} item={item} claiming={claimingId === item.id} onClaim={claim} />
                      ))}
                    </div>
                  ) : (
                    <p className="queue-empty-note">اقدام بازی در این فیلتر وجود ندارد.</p>
                  )}
                </Panel>

                <Panel>
                  <div className="section-heading">
                    <div>
                      <h2>در حال رسیدگی</h2>
                      <p>مواردی که وضعیت آن‌ها در سامانه «در حال رسیدگی» است</p>
                    </div>
                    <Badge tone="neutral">{claimedItems.length.toLocaleString("fa-IR")} مورد</Badge>
                  </div>
                  {claimedItems.length ? (
                    <div className="queue-list">
                      {claimedItems.map((item) => (
                        <WorkItemRow key={item.id} item={item} claiming={false} onClaim={claim} />
                      ))}
                    </div>
                  ) : (
                    <p className="queue-empty-note">موردی با وضعیت در حال رسیدگی وجود ندارد.</p>
                  )}
                </Panel>
              </div>

              <aside className="queue-aside" aria-label="خلاصه موعدها">
                <Panel>
                  <div className="section-heading">
                    <h2>عقب‌افتاده</h2>
                    <Badge tone={overdueItems.length ? "warning" : "neutral"}>
                      {overdueItems.length.toLocaleString("fa-IR")}
                    </Badge>
                  </div>
                  {overdueItems.length ? (
                    <ul className="queue-compact-list">
                      {overdueItems.slice(0, 4).map((item) => (
                        <li key={item.id}>
                          <strong>{item.title}</strong>
                          <span>{typeLabels[item.work_type]} · {dueLabel(item.due_at)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="queue-empty-note">اقدام عقب‌افتاده‌ای ثبت نشده است.</p>}
                </Panel>

                <Panel>
                  <div className="section-heading">
                    <h2>پیش رو</h2>
                    <Badge tone="accent">{upcomingItems.length.toLocaleString("fa-IR")}</Badge>
                  </div>
                  {upcomingItems.length ? (
                    <ul className="queue-compact-list">
                      {upcomingItems.slice(0, 5).map((item) => (
                        <li key={item.id}>
                          <strong>{item.title}</strong>
                          <span>{dateOnly.format(new Date(item.due_at!))}</span>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="queue-empty-note">موعدی در هفت روز آینده ثبت نشده است.</p>}
                </Panel>
              </aside>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
