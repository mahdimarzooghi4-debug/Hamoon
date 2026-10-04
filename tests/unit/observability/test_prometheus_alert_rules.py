from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

POLICY = Path("ops/observability/alert-policy.json")
RULES = Path("ops/observability/prometheus/hamoon-alerts.yml")


def _run(rules: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_prometheus_alert_rules.py",
            str(POLICY),
            str(rules),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_materialized_prometheus_rules_match_alert_policy() -> None:
    result = _run(RULES)

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_materialized_rules_reject_expression_drift(tmp_path: Path) -> None:
    value = json.loads(RULES.read_text())
    value["groups"][0]["rules"][0]["expr"] = "vector(0)"
    candidate = tmp_path / "rules.yml"
    candidate.write_text(json.dumps(value), encoding="utf-8")

    result = _run(candidate)

    assert result.returncode != 0
    assert "expression mismatch" in result.stderr


def test_materialized_rules_reject_runbook_drift(tmp_path: Path) -> None:
    value = json.loads(RULES.read_text())
    value["groups"][0]["rules"][0]["annotations"]["runbook"] = "wrong"
    candidate = tmp_path / "rules.yml"
    candidate.write_text(json.dumps(value), encoding="utf-8")

    result = _run(candidate)

    assert result.returncode != 0
    assert "runbook mismatch" in result.stderr
