import { useEffect, useState } from "react";

import {
  getEmpowermentOverview,
  type EBand,
  type EmpowermentOverview,
  type OutcomeClassification,
  type PGORDistribution,
  type PGORVariable,
} from "../api/empowerment";
import {
  Badge,
  ErrorState,
  LoadingState,
  MetricCard,
  Panel,
} from "../design-system/components";

type OverviewState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; data: EmpowermentOverview };

const variableLabels: Record<PGORVariable, string> = {
  P: "مشارکت",
  G: "ظرفیت رشد",
  O: "فرصت",
  R: "تاب‌آوری",
};

const eBandLabels: Record<EBand, string> = {
  SEVERE_CRISIS: "بحران شدید",
  VULNERABLE: "آسیب‌پذیر",
  SUPPORTED_EMPOWERMENT: "توانمندی با حمایت",
  ECONOMIC_SOCIAL_INDEPENDENCE: "استقلال اقتصادی ـ اجتماعی",
};

const outcomeLabels: Record<OutcomeClassification, string> = {
  GOAL_ACHIEVED: "هدف محقق شده",
  PROGRESS: "پیشرفت",
  NO_SIGNIFICANT_CHANGE: "بدون تغییر معنادار",
  REGRESSION: "پسرفت",
  NEEDS_MORE_TIME: "نیازمند زمان بیشتر",
  NEEDS_MORE_DATA: "نیازمند داده بیشتر",
};

function count(value: number): string {
  return value.toLocaleString("fa-IR");
}

function score(value: string | number | null): string {
  if (value === null) return "—";
  return Number(value).toLocaleString("fa-IR", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  });
}

function DistributionCard({
  code,
  distribution,
}: {
  code: "P" | "G" | "O" | "R" | "E";
  distribution: PGORDistribution;
}) {
  const label = code === "E" ? "شاخص توانمندسازی E" : variableLabels[code];

  return (
    <article className="empowerment-distribution-card">
      <div>
        <span>{code}</span>
        <strong>{label}</strong>
      </div>
      <b>{score(distribution.mean)}</b>
      <small>
        کمینه {score(distribution.minimum)}
        {" · "}
        بیشینه {score(distribution.maximum)}
      </small>
    </article>
  );
}

function CountBar({
  label,
  value,
  maximum,
}: {
  label: string;
  value: number;
  maximum: number;
}) {
  const width = maximum > 0 ? Math.max(4, (value / maximum) * 100) : 0;

  return (
    <div className="empowerment-count-row">
      <div>
        <span>{label}</span>
        <strong>{count(value)}</strong>
      </div>
      <div className="empowerment-count-track" aria-hidden="true">
        <span style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

export function EmpowermentOverviewPage() {
  const [state, setState] = useState<OverviewState>({ kind: "loading" });

  useEffect(() => {
    let mounted = true;
    getEmpowermentOverview()
      .then((data) => {
        if (mounted) setState({ kind: "ready", data });
      })
      .catch(() => {
        if (mounted) setState({ kind: "error" });
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (state.kind === "loading") {
    return <LoadingState label="در حال ساخت نمای تجمیعی توانمندسازی…" />;
  }

  if (state.kind === "error") {
    return (
      <ErrorState
        title="نمای توانمندسازی دریافت نشد"
        description="این نما به نقش مدیریتی و unit_id معتبر در نشست سازمانی نیاز دارد."
      />
    );
  }

  const { data } = state;
  const eBandMax = Math.max(0, ...Object.values(data.e_band_counts));
  const bottleneckMax = Math.max(0, ...Object.values(data.bottleneck_counts));
  const outcomeMax = Math.max(0, ...Object.values(data.outcome_counts));

  return (
    <div className="page-stack empowerment-overview-page">
      <header className="admin-learning-hero">
        <div>
          <span className="eyebrow">PB-112 · Aggregated Analytics</span>
          <h1>نمای توانمندسازی</h1>
          <p>
            فقط داده تجمیعی واحد سازمانی مجاز نمایش داده می‌شود. هر Household
            در توزیع PGOR با آخرین snapshot رسمی خود یک‌بار شمرده می‌شود.
          </p>
        </div>
        <Badge tone="accent">واحد {data.scope_unit_id}</Badge>
      </header>

      <div className="admin-metric-grid">
        <MetricCard
          label="پرونده‌های واحد"
          value={count(data.household_count)}
        />
        <MetricCard
          label="دارای PGOR رسمی"
          value={count(data.households_with_official_pgor)}
        />
        <MetricCard
          label="Outcome بازبینی‌نشده"
          value={count(data.unreviewed_outcomes)}
        />
      </div>

      <Panel className="admin-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">PGOR Distribution</span>
            <h2>توزیع عددی آخرین PGOR رسمی</h2>
          </div>
          <Badge tone="accent">۰ تا ۱</Badge>
        </div>
        <div className="empowerment-distribution-grid">
          <DistributionCard code="P" distribution={data.p} />
          <DistributionCard code="G" distribution={data.g} />
          <DistributionCard code="O" distribution={data.o} />
          <DistributionCard code="R" distribution={data.r} />
          <DistributionCard code="E" distribution={data.e} />
        </div>
      </Panel>

      <div className="empowerment-two-column">
        <Panel className="admin-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">E Bands</span>
              <h2>سطوح توانمندسازی</h2>
            </div>
          </div>
          <div className="empowerment-count-list">
            {(Object.entries(data.e_band_counts) as [EBand, number][]).map(
              ([band, value]) => (
                <CountBar
                  key={band}
                  label={eBandLabels[band]}
                  value={value}
                  maximum={eBandMax}
                />
              ),
            )}
          </div>
        </Panel>

        <Panel className="admin-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Bottlenecks</span>
              <h2>گلوگاه‌های PGOR</h2>
            </div>
          </div>
          <div className="empowerment-count-list">
            {(Object.entries(data.bottleneck_counts) as [PGORVariable, number][]).map(
              ([variable, value]) => (
                <CountBar
                  key={variable}
                  label={`${variable} · ${variableLabels[variable]}`}
                  value={value}
                  maximum={bottleneckMax}
                />
              ),
            )}
          </div>
          <p className="empowerment-note">
            در حالت tie همه متغیرهای گلوگاه persisted شمرده می‌شوند؛ بنابراین
            جمع این بخش می‌تواند از تعداد Householdهای دارای PGOR بیشتر باشد.
          </p>
        </Panel>
      </div>

      <Panel className="admin-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Outcome Counts</span>
            <h2>نتایج بازبینی‌شده</h2>
          </div>
        </div>
        <div className="empowerment-outcome-grid">
          {(
            Object.entries(data.outcome_counts) as [
              OutcomeClassification,
              number,
            ][]
          ).map(([classification, value]) => (
            <CountBar
              key={classification}
              label={outcomeLabels[classification]}
              value={value}
              maximum={outcomeMax}
            />
          ))}
        </div>
      </Panel>
    </div>
  );
}
