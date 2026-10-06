import json
from pathlib import Path

from hamoon.infrastructure.ai.gemma4_baseline import (
    GEMMA4_BASELINE_MODEL_ID,
    GEMMA4_BASELINE_MODEL_SHA256,
    GEMMA4_BASELINE_REVISION,
    GEMMA4_BASELINE_TOKENIZER_SHA256,
)


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
    "internal_model_fail_safe_configured",
    "gemma4_checkpoint_attested",
    "gemma4_checkpoint_provisioned",
    "provider_dispatch_configured",
    "backup_policy_configured",
    "retention_policy_configured",
]


def test_runtime_preflight_contract_is_explicit_and_stable() -> None:
    path = Path("ops/production/runtime-preflight.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 3
    assert payload["contract"] == "HAMOON_PRODUCTION_RUNTIME_PREFLIGHT"
    assert payload["required_checks"] == EXPECTED_CHECKS
    assert len(payload["required_checks"]) == len(set(payload["required_checks"]))
    checkpoint = payload["internal_model_checkpoint"]
    assert checkpoint == {
        "model_id": GEMMA4_BASELINE_MODEL_ID,
        "revision": GEMMA4_BASELINE_REVISION,
        "model_sha256": GEMMA4_BASELINE_MODEL_SHA256,
        "tokenizer_sha256": GEMMA4_BASELINE_TOKENIZER_SHA256,
        "execution_mode": "IN_PROCESS",
        "network_model_download": False,
    }
    assert payload["internal_model_checkpoint_provisioning"] == {
        "filesystem_scope": "PRIVATE_LOCAL",
        "read_only": True,
        "network_model_download": False,
    }
