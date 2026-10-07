from __future__ import annotations

import json
from pathlib import Path

import yaml


def test_production_secret_consumers_use_production_environment() -> None:
    consumers = set()
    for path in Path(".github/workflows").glob("*.yml"):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in workflow["jobs"].items():
            if "secrets.HAMOON_" not in json.dumps(job):
                continue
            consumers.add(path.name)
            assert job.get("environment") == "production", (path.name, name)

    assert {
        "production-monitoring.yml",
        "external-telemetry.yml",
        "external-alert-delivery.yml",
        "production-recovery-verification.yml",
    } <= consumers
