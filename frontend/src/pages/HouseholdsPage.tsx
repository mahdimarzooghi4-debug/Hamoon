import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import { ApiError } from "../api/client";
import {
  getHousehold,
  getHouseholds,
  type HouseholdSummary,
  type HouseholdStatus,
  type PGORVariable,
} from "../api/households";
import { AppLink, type AppPath } from "../app/navigation";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  Panel,
} from "../design-system/components";

type ListState =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "error" }
  | { kind: "ready"; items: HouseholdSummary[] };

type PreviewState =
  | { kind: "closed" }
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; item: HouseholdSummary };

const lifecycleLabels: Record<HouseholdStatus, string> = {
  DRAFT: "پیش‌نویس",
  ACTIVE: "فعال",
  PAUSED: "متوقف",
  CLOSED: "بسته",
  ARCHIVED: "آرشیو",
};

const variableLabels: Record<PGORVariable, string> = {
  P: "مشارکت",
  G: "ظرفیت رشد",
  O: "فرصت",
  R: "تاب‌آوری",
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

const persianDate = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
});

function householdPath(id: string): AppPath {
  return `/households/${id}`;
}

function numberValue(value: string | number): number {
  return typeof value === "number" ? value : Number(value);
}

function eLabel(item: HouseholdSummary): string {
  if (item.pgor === null) return "—";
  return numberValue(item.pgor.e).toLocaleString("fa-IR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function bottleneckLabel(item: HouseholdSummary): string {
  if (item.pgor === null || item.pgor.bottleneck_variables.length === 0) {
    return "—";
  }
  return item.pgor.bottleneck_variables
    .map((variable) => `${variableLabels[variable]} — ${variable}`)
    .join("، ");
}

function interventionLabel(item: HouseholdSummary): string {
  if (item.current_intervention === null) return "بدون مداخله جاری";
  return interventionLabels[item.current_intervention.intervention_type]
    ?? item.current_intervention.intervention_type;
}

function isOverdue(item: HouseholdSummary): boolean {
  const due = item.next_work_item?.due_at;
  return due !== null && due !== undefined && new Date(due).getTime() < Date.now();
}

function statusTone(status: HouseholdStatus): "success" | "warning" | "neutral" {
  if (status === "ACTIVE") return "success";
  if (status === "PAUSED" || status === "DRAFT") return "warning";
  return "neutral";
}

export function HouseholdsPage() {
  const [state, setState] = useState<ListState>({ kind: "loading" });
  const [query, setQuery] = useState("");
  const [preview, setPreview] = useState<PreviewState>({ kind: "closed" });

  const load = useCallback(async (value: string) => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "ready", items: await getHouseholds(value) });
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
        setState({ kind: "auth-required" });
      } else {
        setState({ kind: "error" });
      }
    }
  }, []);

  useEffect(() => {
    void load("");
  }, [load]);

  const items = state.kind === "ready" ? state.items : [];
  const summary = useMemo(
    () => ({
      total: items.length,
      active: items.filter((item) => item.lifecycle_status === "ACTIVE").length,
      measured: items.filter((item) => item.pgor !== null).length,
      attention: items.filter(isOverdue).length,
    }),
    [items],
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void load(query);
  }

  async function openPreview(householdId: string) {
    setPreview({ kind: "loading" });
    try {
      setPreview({ kind: "ready", item: await getHousehold(householdId) });
    } catch {
      setPreview({ kind: "error" });
    }
  }

  return (
    <div className="page-stack">
      <header className="page-heading">
        <div>
          <span className="eyebrow">پرونده‌های تحت مسئولیت شما</span>
          <h1>پرونده‌های من</h1>
          <p>فقط پرونده‌هایی که assignment فعال برای شما دارند نمایش داده می‌شوند.</p>
        </div>
      </header>

      <section className="metric-grid" aria-label="خلاصه پرونده‌ها">
        <MetricCard label="پرونده‌های این فهرست" value={state.kind === "ready" ? summary.total : "—"} />
        <MetricCard label="فعال" value={state.kind === "ready" ? summary.active : "—"} />
        <MetricCard label="دارای PGOR رسمی" value={state.kind === "ready" ? summary.measured : "—"} />
        <MetricCard label="نیازمند توجه موعد" value={state.kind === "ready" ? summary.attention : "—"} />
      </section>

      <Panel>
        <form className="case-search" onSubmit={submitSearch}>
          <label htmlFor="case-search">جست‌وجوی کد پرونده</label>
          <div className="case-search__controls">
            <input
              id="case-search"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="مثال: H-1405"
              type="search"
              value={query}
            />
            <Button type="submit">جست‌وجو</Button>
            {query.length > 0 ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setQuery("");
                  void load("");
                }}
              >
                پاک کردن
              </Button>
            ) : null}
          </div>
        </form>

        {state.kind === "loading" ? <LoadingState label="در حال دریافت پرونده‌ها…" /> : null}
        {state.kind === "auth-required" ? (
          <EmptyState
            title="ورود سازمانی لازم است"
            description="بدون توکن معتبر هیچ پرونده‌ای از API دریافت نمی‌شود."
          />
        ) : null}
        {state.kind === "error" ? (
          <ErrorState
            description="فهرست پرونده‌ها دریافت نشد."
            action={<Button variant="secondary" onClick={() => void load(query)}>تلاش دوباره</Button>}
          />
        ) : null}
        {state.kind === "ready" && items.length === 0 ? (
          <EmptyState
            title="پرونده‌ای پیدا نشد"
            description="برای این جست‌وجو یا assignment فعلی، پرونده‌ای در دسترس نیست."
          />
        ) : null}

        {state.kind === "ready" && items.length > 0 ? (
          <div className="case-list">
            {items.map((item) => (
              <article className="case-row" key={item.id}>
                <div className="case-row__identity">
                  <strong>پرونده {item.case_code}</strong>
                  <span className="ltr-value">{item.id}</span>
                </div>

                <div className="case-row__cell">
                  <span>وضعیت</span>
                  <Badge tone={statusTone(item.lifecycle_status)}>
                    {lifecycleLabels[item.lifecycle_status]}
                  </Badge>
                </div>

                <div className="case-row__cell">
                  <span>E رسمی</span>
                  <strong className="case-row__e">E {eLabel(item)}</strong>
                </div>

                <div className="case-row__cell">
                  <span>گلوگاه</span>
                  <strong>{bottleneckLabel(item)}</strong>
                </div>

                <div className="case-row__cell">
                  <span>مداخله جاری</span>
                  <strong>{interventionLabel(item)}</strong>
                </div>

                <div className="case-row__cell">
                  <span>اقدام بعدی</span>
                  <strong>{item.next_work_item?.title ?? "اقدام بازی ثبت نشده"}</strong>
                  {isOverdue(item) ? <Badge tone="danger">از موعد گذشته</Badge> : null}
                </div>

                <div className="case-row__actions">
                  <Button variant="secondary" onClick={() => void openPreview(item.id)}>
                    پیش‌نمایش
                  </Button>
                  <AppLink className="hm-button hm-button--primary" to={householdPath(item.id)}>
                    باز کردن پرونده
                  </AppLink>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </Panel>

      {preview.kind !== "closed" ? (
        <div
          className="drawer-backdrop"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) setPreview({ kind: "closed" });
          }}
          role="presentation"
        >
          <aside className="case-drawer" aria-label="پیش‌نمایش پرونده">
            <div className="case-drawer__top">
              <strong>پیش‌نمایش سریع</strong>
              <button
                aria-label="بستن پیش‌نمایش"
                className="drawer-close"
                onClick={() => setPreview({ kind: "closed" })}
                type="button"
              >
                ×
              </button>
            </div>

            {preview.kind === "loading" ? <LoadingState /> : null}
            {preview.kind === "error" ? (
              <ErrorState description="اطلاعات پیش‌نمایش دریافت نشد." />
            ) : null}
            {preview.kind === "ready" ? (
              <div className="drawer-content">
                <div className="drawer-title">
                  <div>
                    <h2>پرونده {preview.item.case_code}</h2>
                    <span>نسخه {preview.item.version.toLocaleString("fa-IR")}</span>
                  </div>
                  <Badge tone={statusTone(preview.item.lifecycle_status)}>
                    {lifecycleLabels[preview.item.lifecycle_status]}
                  </Badge>
                </div>

                <div className="drawer-score">
                  <span>شاخص توانمندسازی</span>
                  <strong>E {eLabel(preview.item)}</strong>
                  <small>
                    {preview.item.pgor === null
                      ? "PGOR رسمی هنوز موجود نیست"
                      : `محاسبه رسمی: ${persianDate.format(new Date(preview.item.pgor.calculated_at))}`}
                  </small>
                </div>

                <div className="drawer-facts">
                  <div>
                    <span>گلوگاه اصلی</span>
                    <strong>{bottleneckLabel(preview.item)}</strong>
                  </div>
                  <div>
                    <span>مداخله جاری</span>
                    <strong>{interventionLabel(preview.item)}</strong>
                  </div>
                  <div>
                    <span>اقدام بعدی</span>
                    <strong>{preview.item.next_work_item?.title ?? "اقدام بازی ثبت نشده"}</strong>
                  </div>
                </div>

                <AppLink
                  className="hm-button hm-button--primary drawer-primary"
                  to={householdPath(preview.item.id)}
                >
                  باز کردن پرونده کامل
                </AppLink>
              </div>
            ) : null}
          </aside>
        </div>
      ) : null}
    </div>
  );
}
