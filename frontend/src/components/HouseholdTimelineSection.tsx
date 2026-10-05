import { useEffect, useState } from "react";

import {
  getHouseholdTimeline,
  type HouseholdTimelineItem,
  type HouseholdTimelineKind,
} from "../api/households";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
} from "../design-system/components";

type TimelineState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: HouseholdTimelineItem[] };

const kindLabels: Record<HouseholdTimelineKind, string> = {
  FACT: "داده خانوار",
  ASSESSMENT: "ارزیابی",
  PGOR: "محاسبه PGOR",
  DIAGNOSIS: "تشخیص",
  PRESCRIPTION: "نسخه مداخله",
  REFERRAL: "ارجاع",
  PROVIDER_RESULT: "نتیجه ارائه‌دهنده",
  OUTCOME: "پیامد",
};

const statusLabels: Record<string, string> = {
  RECORDED: "ثبت‌شده",
  DRAFT: "پیش‌نویس",
  IN_PROGRESS: "در حال انجام",
  COMPLETED: "تکمیل‌شده",
  OFFICIAL: "رسمی",
  UNDER_REVIEW: "در انتظار بازبینی",
  ACCEPTED: "پذیرفته‌شده",
  CONFIRMED: "تأییدشده",
  MODIFIED: "اصلاح‌شده",
  READY: "آماده",
  SENT: "ارسال‌شده",
  ACTIVE: "فعال",
  CANCELLED: "لغوشده",
  REVIEW_REQUIRED: "نیازمند بازبینی",
};

const detailLabels: Record<string, string> = {
  BASELINE: "ارزیابی پایه",
  REASSESSMENT: "ارزیابی مجدد",
  SEVERE_CRISIS: "بحران شدید",
  VULNERABLE: "آسیب‌پذیر",
  SUPPORTED_EMPOWERMENT: "توانمندسازی حمایتی",
  ECONOMIC_SOCIAL_INDEPENDENCE: "استقلال اقتصادی و اجتماعی",
};

const persianDateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function timelineDetail(detail: string | null): string | null {
  if (detail === null) return null;
  if (detail.startsWith("E_BAND:")) {
    const value = detail.slice("E_BAND:".length);
    return `سطح E: ${detailLabels[value] ?? value}`;
  }
  return detailLabels[detail] ?? detail;
}

export function HouseholdTimelineSection({
  householdId,
}: {
  householdId: string;
}) {
  const [state, setState] = useState<TimelineState>({ kind: "loading" });

  useEffect(() => {
    let mounted = true;
    setState({ kind: "loading" });

    getHouseholdTimeline(householdId)
      .then((items) => {
        if (mounted) setState({ kind: "ready", items });
      })
      .catch(() => {
        if (mounted) setState({ kind: "error" });
      });

    return () => {
      mounted = false;
    };
  }, [householdId]);

  return (
    <Panel className="household-timeline-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">رد زمانی پرونده</span>
          <h2>Timeline خانوار</h2>
        </div>
      </div>

      {state.kind === "loading" ? (
        <LoadingState label="در حال دریافت رویدادهای پرونده…" />
      ) : null}

      {state.kind === "error" ? (
        <ErrorState description="Timeline پرونده دریافت نشد." />
      ) : null}

      {state.kind === "ready" && state.items.length === 0 ? (
        <EmptyState
          title="رویدادی ثبت نشده است"
          description="با ثبت داده، ارزیابی یا اقدام عملیاتی، رویدادها در این بخش ظاهر می‌شوند."
        />
      ) : null}

      {state.kind === "ready" && state.items.length > 0 ? (
        <div className="household-timeline">
          {state.items.map((item) => {
            const detail = timelineDetail(item.detail);
            return (
              <article key={`${item.kind}-${item.entity_id}`}>
                <span className="household-timeline__dot" aria-hidden="true" />
                <div>
                  <div className="household-timeline__heading">
                    <strong>{kindLabels[item.kind]}</strong>
                    <Badge tone="neutral">
                      {statusLabels[item.status] ?? item.status}
                    </Badge>
                  </div>
                  {detail ? <span>{detail}</span> : null}
                  <small>
                    {persianDateTime.format(new Date(item.occurred_at))}
                  </small>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}
    </Panel>
  );
}
