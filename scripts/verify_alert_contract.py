#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_ALERT_IDS = {
    "HAMOON_METRICS_MISSING",
    "HAMOON_API_CRITICAL_ERROR_SPIKE",
    "HAMOON_POSTGRES_UNAVAILABLE",
    "HAMOON_OUTBOX_STUCK",
    "HAMOON_OUTBOX_WORKER_STALE",
    "HAMOON_TEMPORAL_WORKER_STALE",
}
ALLOWED_SEVERITIES = {"critical", "warning"}
FORBIDDEN_LABEL_TERMS = {
    "household_id",
    "referral_id",
    "user_id",
    "request_id",
    "trace_id",
    "national_id",
    "phone",
}
RUNBOOK_HEADINGS = (
    "## Signal",
    "## Diagnosis",
    "## Immediate actions",
    "## Escalation",
    "## Safe recovery",
)
METRIC_RE = re.compile(r"\bhamoon_[a-zA-Z0-9_:]+")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"alert contract invalid: {message}")


def main() -> None:
    require(
        len(sys.argv) == 3,
        "usage: verify_alert_contract.py <policy.json> <repo-root>",
    )
    policy_path = Path(sys.argv[1]).resolve()
    repo_root = Path(sys.argv[2]).resolve()
    require(policy_path.is_file(), f"missing policy {policy_path}")

    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    require(isinstance(policy, dict), "policy must be an object")
    require(policy.get("schema_version") == 1, "unsupported schema")
    require(policy.get("status") == "ENFORCED", "status must be ENFORCED")

    exported = policy.get("exported_metric_families")
    require(isinstance(exported, list) and exported, "exported metrics missing")
    exported_set = {str(value) for value in exported}
    require(len(exported_set) == len(exported), "duplicate exported metrics")

    alerts = policy.get("alerts")
    require(isinstance(alerts, list) and alerts, "alerts missing")
    seen: set[str] = set()

    for raw in alerts:
        require(isinstance(raw, dict), "alert must be an object")
        alert_id = raw.get("id")
        require(
            isinstance(alert_id, str) and re.fullmatch(r"HAMOON_[A-Z0-9_]+", alert_id),
            "alert id invalid",
        )
        require(alert_id not in seen, f"duplicate alert id {alert_id}")
        seen.add(alert_id)

        severity = raw.get("severity")
        require(severity in ALLOWED_SEVERITIES, f"{alert_id} severity invalid")
        duration = raw.get("for_seconds")
        require(
            isinstance(duration, int) and duration >= 60,
            f"{alert_id} for_seconds must be at least 60",
        )
        expression = raw.get("expression")
        require(
            isinstance(expression, str) and expression.strip(),
            f"{alert_id} expression missing",
        )
        lower_expression = expression.lower()
        for term in FORBIDDEN_LABEL_TERMS:
            require(
                term not in lower_expression,
                f"{alert_id} contains forbidden label {term}",
            )

        referenced = set(METRIC_RE.findall(expression))
        require(referenced, f"{alert_id} references no Hamoon metric")
        unknown = referenced - exported_set
        require(not unknown, f"{alert_id} references unexported metrics {sorted(unknown)}")

        summary = raw.get("summary")
        require(
            isinstance(summary, str) and len(summary.strip()) >= 20,
            f"{alert_id} summary too short",
        )
        runbook = raw.get("runbook")
        require(
            isinstance(runbook, str) and runbook.startswith("docs/runbooks/"),
            f"{alert_id} runbook path invalid",
        )
        runbook_path = (repo_root / runbook).resolve()
        require(
            runbook_path.is_relative_to(repo_root),
            f"{alert_id} runbook escapes repository",
        )
        require(runbook_path.is_file(), f"{alert_id} runbook missing")
        text = runbook_path.read_text(encoding="utf-8")
        for heading in RUNBOOK_HEADINGS:
            require(
                heading in text,
                f"{alert_id} runbook missing heading {heading}",
            )

    missing = REQUIRED_ALERT_IDS - seen
    require(not missing, f"required alerts missing {sorted(missing)}")
    print(
        json.dumps(
            {
                "status": "valid",
                "alert_count": len(alerts),
                "critical_alert_count": sum(
                    1 for alert in alerts if alert["severity"] == "critical"
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
