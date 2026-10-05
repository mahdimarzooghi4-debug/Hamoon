import json
from pathlib import Path


EXPECTED_CHECKS = [
    "postgresql_connectivity",
    "nats_jetstream_connectivity",
    "temporal_connectivity",
    "oidc_discovery_https",
    "evidence_s3_private_https",
    "evidence_scanner_https",
    "otlp_traces_https",
    "otlp_logs_https",
    "protected_metrics_configured",
    "provider_dispatch_configured",
    "backup_policy_configured",
    "retention_policy_configured",
]


def test_runtime_preflight_contract_is_explicit_and_stable() -> None:
    path = Path("ops/production/runtime-preflight.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["contract"] == "HAMOON_PRODUCTION_RUNTIME_PREFLIGHT"
    assert payload["required_checks"] == EXPECTED_CHECKS
    assert len(payload["required_checks"]) == len(set(payload["required_checks"]))
