import { useEffect, useState } from "react";

import { ApiError } from "../api/client";
import {
  getHousehold,
  type HouseholdStatus,
  type HouseholdSummary,
  type PGORVariable,
} from "../api/households";
import { AppLink } from "../app/navigation";
import { DiagnosisSection } from "../components/DiagnosisSection";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
} from "../design-system/components";

type DetailState =
  | { kind: "loading" }
  | { kind: "auth-required" }
  | { kind: "not-found" }
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

const bandLabels: Record<string, string> = {
  SEVERE_CRISIS: "بحران شدید",
  VULNERABLE: "آسیب‌پذیر",
  SUPPORTED_EMPOWERMENT: "توانمندسازی حمایتی",
  ECONOMIC_SOCIAL_INDEPENDENCE: "استقلال اقتصادی و اجتماعی",
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

const interventionStatusLabels: Record<string, string> = {
  PLANNED: "برنامه‌ریزی‌شده",
  READY_FOR_REFERRAL: "آماده ارجاع",
  REFERRED: "ارجاع‌شده",
  ACTIVE: "در حال اجرا",
  COMPLETED: "تکمیل‌شده",
  CANCELLED: "لغوشده",
};

const persianDateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function numeric(value: string | number): number {
  return typeof value === "number" ? value : Number(value);
}

function score(value: string | number): string {
  return numeric(value).toLocaleString("fa-IR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function statusTone(status: HouseholdStatus): "success" | "warning" | "neutral" {
  if (status === "ACTIVE") return "success";
  if (status === "PAUSED" || status === "DRAFT") return "warning";
  return "neutral";
}

export function HouseholdPage({ householdId }: { householdId: string }) {
  const [state, setState] = useState<DetailState>({ kind: "loading" });

  useEffect(() => {
    let mounted = true;
    setState({ kind: "loading" });
    getHousehold(householdId)
      .then((item) => {
        if (mounted) setState({ kind: "ready", item });
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
          setState({ kind: "auth-required" });
        } else if (error instanceof ApiError && error.status === 404) {
          setState({ kind: "not-found" });
        } else {
          setState({ kind: "error" });
        }
      });

    return () => {
      mounted = false;
    };
  }, [householdId]);

  if (state.kind === "loading") {
    return <LoadingState label="در حال باز کردن پرونده…" />;
  }

  if (state.kind === "auth-required") {
    return (
      <EmptyState
        title="ورود سازمانی لازم است"
        description="برای مشاهده پرونده باید توکن دسترسی معتبر داشته باشید."
      />
    );
  }

  if (state.kind === "not-found") {
    return (
      <ErrorState
        title="پرونده پیدا نشد"
        description="پرونده وجود ندارد یا دیگر در دسترس شما نیست."
        action={<AppLink className="hm-button hm-button--secondary" to="/households">بازگشت به پرونده‌ها</AppLink>}
      />
    );
  }

  if (state.kind === "error") {
    return <ErrorState description="اطلاعات پرونده دریافت نشد." />;
  }

  const item = state.item;
  const pgor = item.pgor;

  return (
    <div className="page-stack">
      <header className="case-header">
        <div className="case-header__main">
          <AppLink className="text-link" to="/households">پرونده‌های من ←</AppLink>
          <div className="case-header__title">
            <div>
              <span className="eyebrow">پرونده هوشمند خانوار</span>
              <h1>پرونده {item.case_code}</h1>
            </div>
            <Badge tone={statusTone(item.lifecycle_status)}>
              {lifecycleLabels[item.lifecycle_status]}
            </Badge>
          </div>
          <div className="case-header__meta">
            <span>نسخه {item.version.toLocaleString("fa-IR")}</span>
            {item.organizational_unit_id ? (
              <span>واحد: {item.organizational_unit_id}</span>
            ) : null}
            <span className="ltr-value">شناسه: {item.id}</span>
          </div>
        </div>
      </header>

      <section className="case-overview-grid">
        <Panel className="pgor-panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">محاسبه قطعی سامانه</span>
              <h2>وضعیت PGOR</h2>
            </div>
            {pgor ? <Badge tone="accent">{bandLabels[pgor.e_band] ?? pgor.e_band}</Badge> : null}
          </div>

          {pgor === null ? (
            <EmptyState
              title="PGOR رسمی هنوز وجود ندارد"
              description="پس از تکمیل ارزیابی معتبر، snapshot رسمی در این بخش نمایش داده می‌شود."
            />
          ) : (
            <>
              <div className="e-score">
                <span>شاخص توانمندسازی</span>
                <strong>E {score(pgor.e)}</strong>
                <small>{persianDateTime.format(new Date(pgor.calculated_at))}</small>
              </div>

              <div className="pgor-grid">
                {(
                  [
                    ["P", pgor.p],
                    ["G", pgor.g],
                    ["O", pgor.o],
                    ["R", pgor.r],
                  ] as const
                ).map(([code, value]) => (
                  <article className="pgor-metric" key={code}>
                    <span>{variableLabels[code]}</span>
                    <strong>{code} {score(value)}</strong>
                    {pgor.bottleneck_variables.includes(code) ? (
                      <Badge tone="warning">گلوگاه</Badge>
                    ) : null}
                  </article>
                ))}
              </div>

              {pgor.data_quality_flags.length > 0 ? (
                <div className="inline-alert">
                  پرچم‌های کیفیت داده: {pgor.data_quality_flags.join("، ")}
                </div>
              ) : null}
            </>
          )}
        </Panel>

        <div className="case-side-stack">
          <Panel>
            <div className="section-heading">
              <div>
                <span className="eyebrow">اقدام جاری</span>
                <h2>مداخله</h2>
              </div>
            </div>
            {item.current_intervention === null ? (
              <EmptyState
                title="مداخله جاری وجود ندارد"
                description="هیچ مداخله غیرنهایی برای این پرونده ثبت نشده است."
              />
            ) : (
              <div className="summary-card">
                <strong>
                  {interventionLabels[item.current_intervention.intervention_type]
                    ?? item.current_intervention.intervention_type}
                </strong>
                <span>
                  هدف PGOR: {variableLabels[item.current_intervention.target_pgor_variable]}
                  {" — "}
                  {item.current_intervention.target_pgor_variable}
                </span>
                <Badge tone="accent">
                  {interventionStatusLabels[item.current_intervention.status]
                    ?? item.current_intervention.status}
                </Badge>
              </div>
            )}
          </Panel>

          <Panel>
            <div className="section-heading">
              <div>
                <span className="eyebrow">اقدام بعدی مددکار</span>
                <h2>کارتابل پرونده</h2>
              </div>
            </div>
            {item.next_work_item === null ? (
              <EmptyState
                title="اقدام بازی وجود ندارد"
                description="برای این پرونده وظیفه باز یا در حال رسیدگی ثبت نشده است."
              />
            ) : (
              <div className="summary-card">
                <strong>{item.next_work_item.title}</strong>
                <span>{item.next_work_item.reason}</span>
                <div className="summary-card__meta">
                  <Badge tone={item.next_work_item.status === "CLAIMED" ? "accent" : "neutral"}>
                    {item.next_work_item.status === "CLAIMED" ? "در حال رسیدگی" : "باز"}
                  </Badge>
                  <span>
                    {item.next_work_item.due_at
                      ? `موعد: ${persianDateTime.format(new Date(item.next_work_item.due_at))}`
                      : "بدون موعد"}
                  </span>
                </div>
                <AppLink className="hm-button hm-button--secondary" to="/work-queue">
                  رفتن به کارتابل
                </AppLink>
              </div>
            )}
          </Panel>
        </div>
      </section>

      <DiagnosisSection
        householdId={item.id}
        pgorSnapshotId={pgor?.snapshot_id ?? null}
      />

      <Panel>
        <div className="section-heading">
          <div>
            <span className="eyebrow">مسیر Canonical بعدی</span>
            <h2>نسخه توانمندسازی و مداخلات</h2>
          </div>
        </div>
        <EmptyState
          title="نسخه توانمندسازی در vertical slice بعدی متصل می‌شود"
          description="پس از نهایی‌شدن تصمیم تشخیص، پیشنهاد نسخه، تصمیم انسانی و مداخلات از APIهای واقعی به همین پرونده متصل می‌شوند."
        />
      </Panel>
    </div>
  );
}
