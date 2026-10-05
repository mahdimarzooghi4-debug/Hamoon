import { useEffect, useState } from "react";

import {
  getPGORTrace,
  type PGORTrace,
  type PGORTraceInput,
} from "../api/households";
import {
  Badge,
  ErrorState,
  LoadingState,
  Panel,
} from "../design-system/components";

type TraceState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; trace: PGORTrace };

const variableLabels: Record<PGORTraceInput["variable_code"], string> = {
  P: "مشارکت",
  G: "ظرفیت رشد",
  O: "فرصت",
  R: "تاب‌آوری",
};

function score(value: string | number): string {
  const numeric = typeof value === "number" ? value : Number(value);
  return numeric.toLocaleString("fa-IR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

function shortId(value: string): string {
  return value.length <= 16
    ? value
    : `${value.slice(0, 8)}…${value.slice(-6)}`;
}

export function PGORTraceSection({ snapshotId }: { snapshotId: string }) {
  const [state, setState] = useState<TraceState>({ kind: "loading" });

  useEffect(() => {
    let mounted = true;
    setState({ kind: "loading" });

    getPGORTrace(snapshotId)
      .then((trace) => {
        if (mounted) setState({ kind: "ready", trace });
      })
      .catch(() => {
        if (mounted) setState({ kind: "error" });
      });

    return () => {
      mounted = false;
    };
  }, [snapshotId]);

  return (
    <Panel>
      <div className="section-heading">
        <div>
          <span className="eyebrow">رد محاسبه ذخیره‌شده</span>
          <h2>Trace تاریخی PGOR</h2>
        </div>
        <Badge tone="accent">بدون محاسبه مجدد</Badge>
      </div>

      {state.kind === "loading" ? (
        <LoadingState label="در حال دریافت ورودی‌های تاریخی PGOR…" />
      ) : null}

      {state.kind === "error" ? (
        <ErrorState description="رد محاسبه تاریخی PGOR دریافت نشد." />
      ) : null}

      {state.kind === "ready" ? (
        <>
          <div className="pgor-grid">
            <article className="pgor-metric">
              <span>نسخه تعریف</span>
              <strong>{state.trace.definition_version}</strong>
            </article>
            <article className="pgor-metric">
              <span>نسخه موتور</span>
              <strong>{state.trace.engine_version}</strong>
            </article>
            <article className="pgor-metric">
              <span>نسخه امتیازدهی</span>
              <strong>{state.trace.scoring_version}</strong>
            </article>
            <article className="pgor-metric">
              <span>اثر انگشت ورودی</span>
              <strong className="ltr-value">
                {shortId(state.trace.input_fingerprint)}
              </strong>
            </article>
          </div>

          <div className="inline-alert">
            این بخش فقط ورودی‌های persisted همان snapshot را نمایش می‌دهد؛
            هیچ PGOR جدیدی در frontend یا backend محاسبه نمی‌شود.
          </div>

          <div className="referral-timeline">
            {state.trace.inputs.map((item) => (
              <article
                key={`${item.indicator_definition_id}-${item.observation_id}`}
              >
                <span className="referral-timeline__dot" aria-hidden="true" />
                <div>
                  <strong>
                    {item.indicator_name_fa} · {variableLabels[item.variable_code]}
                  </strong>
                  <span>
                    {item.dimension_name_fa} · خام {score(item.raw_score_0_100)}
                    {" · "}
                    نرمال‌شده {score(item.normalized_score)}
                  </span>
                  <small className="ltr-value">
                    observation {shortId(item.observation_id)} · v
                    {item.observation_version.toLocaleString("fa-IR")}
                  </small>
                </div>
              </article>
            ))}
          </div>
        </>
      ) : null}
    </Panel>
  );
}
