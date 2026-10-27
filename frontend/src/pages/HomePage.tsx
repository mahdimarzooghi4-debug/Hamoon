import { useCallback, useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../api/client";
import { beginLogin } from "../auth/oidc";
import { getHouseholds, type HouseholdStatus, type HouseholdSummary } from "../api/households";
import { getWorkQueue, type WorkItem } from "../api/operations";
import { AppLink, type AppPath } from "../app/navigation";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
} from "../design-system/components";

type HomeState =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "error" }
  | { kind: "ready"; households: HouseholdSummary[]; workItems: WorkItem[] };

const householdStatusLabels: Record<HouseholdStatus, string> = {
  DRAFT: "پیش‌نویس",
  ACTIVE: "فعال",
  PAUSED: "متوقف",
  CLOSED: "بسته",
  ARCHIVED: "بایگانی",
};

function householdTone(status: HouseholdStatus): "success" | "warning" | "neutral" {
  if (status === "ACTIVE") return "success";
  if (status === "DRAFT" || status === "PAUSED") return "warning";
  return "neutral";
}

function householdPath(id: string): AppPath {
  return `/households/${id}`;
}

function pgorValue(household: HouseholdSummary): string {
  if (household.pgor === null) return "—";
  const value = Number(household.pgor.e);
  return Number.isFinite(value)
    ? value.toLocaleString("fa-IR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "—";
}

function isDueToday(item: WorkItem, now = new Date()): boolean {
  if (item.due_at === null) return false;
  const due = new Date(item.due_at);
  return due.getFullYear() === now.getFullYear()
    && due.getMonth() === now.getMonth()
    && due.getDate() === now.getDate();
}

function dueLabel(item: WorkItem): string {
  if (item.due_at === null) return "بدون موعد";
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", { dateStyle: "medium" })
    .format(new Date(item.due_at));
}

export function HomePage() {
  const [state, setState] = useState<HomeState>({ kind: "loading" });
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const load = useCallback(async (caseQuery: string) => {
    setState({ kind: "loading" });
    try {
      const [households, workItems] = await Promise.all([
        getHouseholds(caseQuery),
        getWorkQueue(100),
      ]);
      setState({ kind: "ready", households, workItems });
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

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    setSubmittedQuery(value);
    void load(value);
  }

  return (
    <div className="home-dashboard">
      {state.kind === "loading" ? <LoadingState label="در حال دریافت داده‌های پرونده و کارتابل…" /> : null}
      {state.kind === "auth-required" ? (
        <EmptyState
          title="برای مشاهده اطلاعات وارد شوید"
          description="پرونده‌ها و وظایف فقط پس از ورود سازمانی و با دسترسی مجاز دریافت می‌شوند."
          action={<Button onClick={() => void beginLogin("/")}>ورود سازمانی</Button>}
        />
      ) : null}
      {state.kind === "error" ? (
        <ErrorState
          description="داده‌های صفحه اصلی دریافت نشد."
          action={<Button variant="secondary" onClick={() => void load(submittedQuery)}>تلاش دوباره</Button>}
        />
      ) : null}

      {state.kind === "ready" ? (
        <>
          <section className="home-hero" aria-label="جست‌وجوی پرونده و مدل مسیر توانمندسازی">
            <div className="home-hero__intro">
              <Badge tone="accent">موتور هوشمند هامون</Badge>
              <h1>پرونده هوشمند توانمندسازی خانوار</h1>
              <p>برای مشاهده وضعیت و مسیر توانمندسازی، کد پرونده را وارد کنید.</p>
              <form className="home-search" onSubmit={submitSearch}>
                <label className="sr-only" htmlFor="home-case-search">کد پرونده</label>
                <input
                  id="home-case-search"
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="کد پرونده"
                  autoComplete="off"
                />
                <Button type="submit">مشاهده پرونده</Button>
              </form>
              <AppLink className="home-advanced-search" to="/households">
                جست‌وجوی پیشرفته و فهرست پرونده‌ها
              </AppLink>
              <div className="home-stage-labels" aria-label="مراحل مسیر توانمندسازی">
                <span>تشخیص</span><span>اقدام</span><span>سنجش</span><span>یادگیری</span>
              </div>
            </div>

            <div className="home-journey">
              <div className="home-journey__heading">
                <strong>مدل مسیر توانمندسازی</strong>
                <span>نمایش خنثی · آماده تحلیل خانوار</span>
              </div>
              <div className="home-journey__visual" aria-hidden="true">
                <span className="home-journey__halo" />
                <span className="home-journey__core" />
                <span className="home-journey__ring home-journey__ring--one" />
                <span className="home-journey__ring home-journey__ring--two" />
                <span className="home-journey__ring home-journey__ring--three" />
              </div>
              <div className="home-journey__stages">
                <div><i />استقلال پایدار</div>
                <div><i />آستانه توانمندی</div>
                <div><i />توانمندسازی</div>
                <div><i />وابستگی</div>
              </div>
              <div className="home-journey__footer">
                <span>مشارکت</span><span>ظرفیت رشد</span><span>فرصت</span><span>تاب‌آوری</span>
              </div>
            </div>
          </section>

          <section className="home-metrics" aria-label="خلاصه داده‌های دریافت‌شده">
            <MetricCard label="پرونده در فهرست دریافت‌شده" value={state.households.length} />
            <MetricCard label="دارای PGOR رسمی" value={state.households.filter((item) => item.pgor !== null).length} />
            <MetricCard label="مداخلات در حال اجرا" value={state.households.filter((item) => item.current_intervention?.status === "ACTIVE").length} />
            <MetricCard label="موعدهای امروز" value={state.workItems.filter((item) => isDueToday(item)).length} />
          </section>

          <section className="home-action-strip" aria-label="وظایف کارتابل">
            {state.workItems.slice(0, 5).map((item) => (
              <AppLink className="home-action" key={item.id} to="/work-queue">
                <span>{item.title}</span>
                <small>{dueLabel(item)}</small>
              </AppLink>
            ))}
            {state.workItems.length === 0 ? (
              <div className="home-action home-action--empty">وظیفه‌ای در کارتابل دریافت نشده است.</div>
            ) : null}
            <AppLink className="home-action home-action--all" to="/work-queue">
              مشاهده کارتابل
            </AppLink>
          </section>

          <section className="home-lower-grid">
            <aside className="home-overview">
              <div className="home-overview__brand"><span className="brand__mark" aria-hidden="true"><i /><i /><i /></span><div><strong>پیش‌نمایش هامون</strong><small>مسیر توانمندسازی هوشمند</small></div></div>
              <p>مقادیر پرونده و شاخص‌ها از داده‌های مجاز سامانه دریافت می‌شوند. تصمیم‌های انسانی جای خود را به پیشنهادهای هوشمند نمی‌دهند.</p>
              <div className="home-overview__facts">
                <span>{state.households.filter((item) => item.lifecycle_status === "ACTIVE").length.toLocaleString("fa-IR")} پرونده فعال در فهرست</span>
                <span>{state.workItems.filter((item) => item.is_overdue).length.toLocaleString("fa-IR")} اقدام دارای تأخیر</span>
              </div>
              <AppLink className="home-overview__link" to="/households">مشاهده همه پرونده‌ها ←</AppLink>
            </aside>

            <section className="home-households" aria-labelledby="home-households-title">
              <header className="home-section-heading">
                <div>
                  <h2 id="home-households-title">{submittedQuery ? "نتایج جست‌وجو" : "پرونده‌های در دسترس"}</h2>
                  <p>نمایش بر اساس پرونده‌های مجاز دریافتی از سامانه</p>
                </div>
                <AppLink className="text-link" to="/households">مشاهده همه ←</AppLink>
              </header>
              {state.households.length === 0 ? (
                <EmptyState
                  title={submittedQuery ? "پرونده‌ای با این کد پیدا نشد" : "پرونده‌ای در دسترس نیست"}
                  description="فهرست بر اساس مجوز و assignment فعال شما از سرویس پرونده دریافت می‌شود."
                />
              ) : (
                <div className="home-households__table" role="table" aria-label="فهرست پرونده‌ها">
                  <div className="home-households__row home-households__row--head" role="row">
                    <span role="columnheader">کد پرونده</span>
                    <span role="columnheader">E رسمی</span>
                    <span role="columnheader">وضعیت</span>
                    <span role="columnheader">اقدام بعدی</span>
                    <span role="columnheader">موعد</span>
                  </div>
                  {state.households.slice(0, 5).map((household) => (
                    <div className="home-households__row" role="row" key={household.id}>
                      <AppLink role="cell" to={householdPath(household.id)}>پرونده {household.case_code}</AppLink>
                      <strong role="cell">{pgorValue(household)}</strong>
                      <span role="cell"><Badge tone={householdTone(household.lifecycle_status)}>{householdStatusLabels[household.lifecycle_status]}</Badge></span>
                      <span role="cell">{household.next_work_item?.title ?? "اقدام بازی ثبت نشده"}</span>
                      <span role="cell">{household.next_work_item ? new Intl.DateTimeFormat("fa-IR-u-ca-persian", { dateStyle: "medium" }).format(household.next_work_item.due_at ? new Date(household.next_work_item.due_at) : new Date()) : "—"}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </section>
        </>
      ) : null}
    </div>
  );
}
