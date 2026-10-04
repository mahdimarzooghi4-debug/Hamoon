#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Prometheus alert rules invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"Prometheus alert rules invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain an object")
    return value


def duration(seconds: int) -> str:
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def main() -> None:
    require(
        len(sys.argv) == 3,
        "usage: verify_prometheus_alert_rules.py <policy.json> <rules.yml>",
    )
    policy = load_json(Path(sys.argv[1]).resolve())
    rules_document = load_json(Path(sys.argv[2]).resolve())

    policy_alerts = policy.get("alerts")
    require(isinstance(policy_alerts, list) and policy_alerts, "policy alerts missing")

    groups = rules_document.get("groups")
    require(isinstance(groups, list) and len(groups) == 1, "exactly one rule group required")
    group = groups[0]
    require(isinstance(group, dict), "rule group invalid")
    require(group.get("name") == "hamoon-production", "rule group name invalid")
    rules = group.get("rules")
    require(isinstance(rules, list), "rules missing")
    require(len(rules) == len(policy_alerts), "rule count differs from policy")

    by_name: dict[str, dict[str, object]] = {}
    for raw in rules:
        require(isinstance(raw, dict), "rule must be an object")
        name = raw.get("alert")
        require(isinstance(name, str) and name, "alert name missing")
        require(name not in by_name, f"duplicate alert rule {name}")
        by_name[name] = raw

    for raw in policy_alerts:
        require(isinstance(raw, dict), "policy alert invalid")
        alert_id = raw.get("id")
        require(isinstance(alert_id, str), "policy alert id invalid")
        require(alert_id in by_name, f"missing materialized rule {alert_id}")
        rule = by_name[alert_id]

        require(rule.get("expr") == raw.get("expression"), f"{alert_id} expression mismatch")
        for_seconds = raw.get("for_seconds")
        require(isinstance(for_seconds, int), f"{alert_id} duration invalid")
        require(rule.get("for") == duration(for_seconds), f"{alert_id} duration mismatch")

        labels = rule.get("labels")
        require(isinstance(labels, dict), f"{alert_id} labels missing")
        require(labels.get("severity") == raw.get("severity"), f"{alert_id} severity mismatch")
        require(labels.get("category") == raw.get("category"), f"{alert_id} category mismatch")
        require(labels.get("service") == "hamoon", f"{alert_id} service label invalid")
        require(
            labels.get("environment") == "production",
            f"{alert_id} environment label invalid",
        )

        annotations = rule.get("annotations")
        require(isinstance(annotations, dict), f"{alert_id} annotations missing")
        require(
            annotations.get("summary") == raw.get("summary"),
            f"{alert_id} summary mismatch",
        )
        require(
            annotations.get("runbook") == raw.get("runbook"),
            f"{alert_id} runbook mismatch",
        )

    print(
        json.dumps(
            {
                "status": "valid",
                "rule_count": len(rules),
                "group": "hamoon-production",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
