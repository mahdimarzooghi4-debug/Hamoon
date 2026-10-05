import { useEffect, useState } from "react";

import {
  getDataHealth,
  getMachineHealth,
  type DataHealth,
  type MachineHealth,
} from "../api/adminHealth";
import {
  Badge,
  ErrorState,
  LoadingState,
  MetricCard,
  Panel,
} from "../design-system/components";

type HealthState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; data: DataHealth; machine: MachineHealth };

const persianDateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  dateStyle: "medium",
  timeStyle: "short",
});

function count(value: number): string {
  return value.toLocaleString("fa-IR");
}

export function AdminHealthPage() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    let mounted = true;
    Promise.all([getDataHealth(), getMachineHealth()])
      .then(([data, machine]) => {
        if (mounted) setState({ kind: "ready", data, machine });
      })
      .catch(() => {
        if (mounted) setState({ kind: "error" });
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (state.kind === "loading") {
    return <LoadingState label="در حال دریافت سلامت داده و ماشین…" />;
  }

  if (state.kind === "error") {
    return (
      <ErrorState
        title="سلامت عملیاتی دریافت نشد"
        description="read-modelهای مدیریتی Data Health و Machine Health در دسترس نیستند."
      />
    );
  }

  return (
    <div className="page-stack admin-health-page">
      <header className="admin-learning-hero">
        <div>
          <span className="eyebrow">Operational Pilot</span>
          <h1>سلامت داده و ماشین</h1>
          <p>
            این صفحه فقط projectionهای عملیاتی persisted را نمایش می‌دهد.
            هیچ تصمیم، PGOR یا policy از اینجا تغییر نمی‌کند.
          </p>
        </div>
        <Badge tone="accent">Admin / Security Auditor</Badge>
      </header>

      <Panel className="admin-health-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">PB-110</span>
            <h2>Data Health</h2>
          </div>
          <span className="admin-health-timestamp">
            {persianDateTime.format(new Date(state.data.generated_at))}
          </span>
        </div>

        <div className="admin-metric-grid">
          <MetricCard
            label="داده ضروریِ ناقص"
            value={count(state.data.missing_required_data)}
            hint="DATA_COMPLETION باز یا در حال رسیدگی"
          />
          <MetricCard
            label="تعارض حل‌نشده"
            value={count(state.data.unresolved_conflicts)}
            hint="Factهای DISPUTED"
          />
          <MetricCard
            label="ارزیابی ناقص"
            value={count(state.data.incomplete_assessments)}
          />
          <MetricCard
            label="منبع منقضی"
            value={count(state.data.stale_source_data)}
            hint="Accepted Fact با effective_to گذشته"
          />
          <MetricCard
            label="خطای Integration"
            value={count(state.data.integration_failures)}
            hint="Inbox / dispatch / outbox unresolved failures"
          />
        </div>

        <div className="admin-health-detail-grid">
          <div>
            <span>در انتظار اعتبارسنجی</span>
            <strong>{count(state.data.pending_validation_facts)}</strong>
          </div>
          <div>
            <span>Work item عقب‌افتاده</span>
            <strong>{count(state.data.overdue_work_items)}</strong>
          </div>
          <div>
            <span>Outbox در انتظار</span>
            <strong>{count(state.data.pending_outbox_messages)}</strong>
          </div>
          <div>
            <span>Evidence قرنطینه</span>
            <strong>{count(state.data.quarantined_evidence)}</strong>
          </div>
        </div>
      </Panel>

      <Panel className="admin-health-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">PB-111</span>
            <h2>Machine Health</h2>
          </div>
          <span className="admin-health-timestamp">
            {persianDateTime.format(new Date(state.machine.generated_at))}
          </span>
        </div>

        <div className="admin-metric-grid">
          <MetricCard
            label="Diagnosis Confirm"
            value={count(state.machine.diagnosis_confirm_total)}
          />
          <MetricCard
            label="Diagnosis Modify"
            value={count(state.machine.diagnosis_modify_total)}
          />
          <MetricCard
            label="Diagnosis Replace"
            value={count(state.machine.diagnosis_replace_total)}
          />
          <MetricCard
            label="Schema Failure"
            value={count(state.machine.schema_failures)}
          />
          <MetricCard
            label="AI Fallback"
            value={count(state.machine.ai_fallback_total)}
            hint="فقط fallback واقعی؛ مقدار صفر به معنی عدم وقوع است"
          />
          <MetricCard
            label="Inference Failure"
            value={count(state.machine.inference_failures)}
          />
          <MetricCard
            label="Workflow Backlog"
            value={count(state.machine.workflow_backlog)}
          />
          <MetricCard
            label="Routing Failure"
            value={count(state.machine.routing_failures)}
          />
        </div>

        <div className="admin-health-detail-grid">
          <div>
            <span>AI Decision</span>
            <strong>{count(state.machine.ai_decisions_total)}</strong>
          </div>
          <div>
            <span>Evaluation Pending</span>
            <strong>{count(state.machine.evaluation_pending)}</strong>
          </div>
          <div>
            <span>Evaluation Failed</span>
            <strong>{count(state.machine.evaluation_failed)}</strong>
          </div>
          <div>
            <span>Routing Policy فعال</span>
            <strong>{count(state.machine.active_routing_policies)}</strong>
          </div>
          <div>
            <span>Reassessment ناتمام</span>
            <strong>{count(state.machine.incomplete_reassessment_plans)}</strong>
          </div>
        </div>
      </Panel>
    </div>
  );
}
