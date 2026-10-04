from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

POLICY = Path("ops/observability/alert-policy.json")


def _run(policy: Path, root: Path = Path(".")) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_alert_contract.py",
            str(policy),
            str(root),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_repository_alert_contract_is_valid() -> None:
    result = _run(POLICY)

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_alert_contract_rejects_sensitive_metric_label(tmp_path: Path) -> None:
    value = json.loads(POLICY.read_text())
    value["alerts"][0]["expression"] = (
        'hamoon_http_requests_total{household_id="household-1"} > 0'
    )
    candidate = tmp_path / "policy.json"
    candidate.write_text(json.dumps(value), encoding="utf-8")

    result = _run(candidate)

    assert result.returncode != 0
    assert "forbidden label household_id" in result.stderr


def test_alert_contract_rejects_unknown_metric(tmp_path: Path) -> None:
    value = json.loads(POLICY.read_text())
    value["alerts"][0]["expression"] = "hamoon_imaginary_metric > 0"
    candidate = tmp_path / "policy.json"
    candidate.write_text(json.dumps(value), encoding="utf-8")

    result = _run(candidate)

    assert result.returncode != 0
    assert "unexported metrics" in result.stderr


def test_alert_contract_rejects_missing_runbook(tmp_path: Path) -> None:
    value = json.loads(POLICY.read_text())
    value["alerts"][0]["runbook"] = "docs/runbooks/DOES_NOT_EXIST.md"
    candidate = tmp_path / "policy.json"
    candidate.write_text(json.dumps(value), encoding="utf-8")

    result = _run(candidate)

    assert result.returncode != 0
    assert "runbook missing" in result.stderr
