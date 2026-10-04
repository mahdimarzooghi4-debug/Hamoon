import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { getWorkQueue, type WorkItem } from "../api/operations";
import { AppLink } from "../app/navigation";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  Panel,
} from "../design-system/components";

type QueueState =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "error" }
  | { kind: "ready"; items: WorkItem[] };

function sameLocalDay(value: Date, target: Date): boolean {
  return (
    value.getFullYear() === target.getFullYear() &&
    value.getMonth() === target.getMonth() &&
    value.getDate() === target.getDate()
  );
}

export function HomePage() {
  const [queue, setQueue] = useState<QueueState>({ kind: "loading" });

  useEffect(() => {
    let mounted = true;
    getWorkQueue(100)
      .then((items) => {
        if (mounted) setQueue({ kind: "ready", items });
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
          setQueue({ kind: "auth-required" });
        } else {
          setQueue({ kind: "error" });
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const metrics = useMemo(() => {
    if (queue.kind !== "ready") return null;
    const now = new Date();
    return {
      all: queue.items.length,
      today: queue.items.filter(
        (item) => item.due_at !== null && sameLocalDay(new Date(item.due_at), now),
      ).length,
      reassessment: queue.items.filter((item) => item.work_type === "REASSESSMENT")
        .length,
      review: queue.items.filter((item) => item.work_type === "OUTCOME_REVIEW").length,
    };
  }, [queue]);

  return (
    <div className="page-stack">
      <section className="hero">
        <div className="hero__copy">
          <Badge tone="accent">مسیر تصمیم و توانمندسازی</Badge>
          <h1>پرونده هوشمند توانمندسازی خانوار</h1>
          <p>
            مشاهده وضعیت، تصمیم‌های انسانی و اقدام‌های موعددار؛ با حفظ مرز روشن میان
            محاسبه قطعی PGOR و پیشنهادهای هوش مصنوعی.
          </p>
          <div className="hero__actions">
            <AppLink className="hm-button hm-button--primary" to="/work-queue">
              مشاهده کارتابل
            </AppLink>
          </div>
        </div>

        <div className="hero__visual" aria-label="مدل مسیر توانمندسازی">
          <div className="orbit" aria-hidden="true">
            <span className="orbit__ring orbit__ring--one" />
            <span className="orbit__ring orbit__ring--two" />
            <span className="orbit__ring orbit__ring--three" />
            <span className="orbit__axis" />
          </div>
          <div className="hero__legend">
            <span>وابستگی</span>
            <span>توانمندسازی</span>
            <span>استقلال پایدار</span>
          </div>
        </div>
      </section>

      <section className="metric-grid" aria-label="خلاصه کارتابل">
        <MetricCard label="همه اقدام‌های باز" value={metrics?.all ?? "—"} />
        <MetricCard label="موعد امروز" value={metrics?.today ?? "—"} />
        <MetricCard label="بازسنجی" value={metrics?.reassessment ?? "—"} />
        <MetricCard label="بازبینی نتیجه" value={metrics?.review ?? "—"} />
      </section>

      <Panel className="home-queue">
        <div className="section-heading">
          <div>
            <span className="eyebrow">اقدام‌های واقعی سامانه</span>
            <h2>کارتابل من</h2>
          </div>
          <AppLink className="text-link" to="/work-queue">مشاهده همه</AppLink>
        </div>

        {queue.kind === "loading" ? <LoadingState /> : null}
        {queue.kind === "auth-required" ? (
          <EmptyState
            title="برای مشاهده کارتابل وارد شوید"
            description="اتصال ورود سازمانی در مرحله یکپارچه‌سازی هویت فعال می‌شود؛ تا آن زمان داده نمونه نمایش داده نمی‌شود."
          />
        ) : null}
        {queue.kind === "error" ? (
          <ErrorState description="ارتباط با سرویس کارتابل برقرار نشد." />
        ) : null}
        {queue.kind === "ready" && queue.items.length === 0 ? (
          <EmptyState
            title="اقدام بازی وجود ندارد"
            description="در حال حاضر هیچ وظیفه باز یا در حال رسیدگی برای شما ثبت نشده است."
          />
        ) : null}
        {queue.kind === "ready" && queue.items.length > 0 ? (
          <div className="compact-list">
            {queue.items.slice(0, 4).map((item) => (
              <article className="compact-item" key={item.id}>
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.reason}</span>
                </div>
                <Badge tone={item.status === "CLAIMED" ? "accent" : "neutral"}>
                  {item.status === "CLAIMED" ? "در حال رسیدگی" : "باز"}
                </Badge>
              </article>
            ))}
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
