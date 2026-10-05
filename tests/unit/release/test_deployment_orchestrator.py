from __future__ import annotations

from typing import cast

import httpx
import pytest

from hamoon.deployment.orchestrator import (
    DeploymentOrchestratorError,
    build_deployment_request,
    build_preflight_request,
    execute_production_deployment,
    execute_production_preflight,
)

COMMIT = "a" * 40
API_IMAGE_ID = "sha256:" + "b" * 64
WEB_IMAGE_ID = "sha256:" + "c" * 64
TOKEN = "t" * 40
PREFLIGHT_CHECKS = [
    "postgresql_connectivity",
    "nats_jetstream_connectivity",
]


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 2,
        "commit_sha": COMMIT,
        "workflow_run_id": "101",
        "backend": {
            "image_id": API_IMAGE_ID,
            "archive": "hamoon-api.tar",
            "archive_sha256": "d" * 64,
        },
        "frontend": {
            "image_id": WEB_IMAGE_ID,
            "archive": "hamoon-web.tar",
            "archive_sha256": "e" * 64,
        },
    }


def _admission() -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "ADMITTED",
        "commit_sha": COMMIT,
        "source_ci_run_id": "101",
        "release_approval_run_id": "303",
        "deployment_admission_run_id": "404",
        "production_target": "hamoon-prod-primary",
        "production_endpoint": "https://hamoon.example.com",
        "expected_deployment_id": "prod-20261005-001",
        "backend_image_id": API_IMAGE_ID,
        "frontend_image_id": WEB_IMAGE_ID,
        "release_manifest_sha256": "f" * 64,
        "release_approval_sha256": "1" * 64,
    }


def _requirements() -> dict[str, object]:
    return {
        "schema_version": 1,
        "contract": "HAMOON_PRODUCTION_RUNTIME_PREFLIGHT",
        "required_checks": PREFLIGHT_CHECKS,
    }


def _preflight_receipt() -> dict[str, object]:
    return {
        "status": "READY",
        "preflight_id": "preflight-001",
        "commit_sha": COMMIT,
        "deployment_id": "prod-20261005-001",
        "production_target": "hamoon-prod-primary",
        "production_endpoint": "https://hamoon.example.com",
        "backend_image_id": API_IMAGE_ID,
        "frontend_image_id": WEB_IMAGE_ID,
        "checks": {check: True for check in PREFLIGHT_CHECKS},
        "checked_at": "2026-10-05T12:55:00+00:00",
    }


def _receipt() -> dict[str, object]:
    return {
        "status": "DEPLOYED",
        "receipt_id": "receipt-001",
        "commit_sha": COMMIT,
        "deployment_id": "prod-20261005-001",
        "production_target": "hamoon-prod-primary",
        "production_endpoint": "https://hamoon.example.com",
        "backend_image_id": API_IMAGE_ID,
        "frontend_image_id": WEB_IMAGE_ID,
        "deployed_at": "2026-10-05T13:00:00+00:00",
    }


def test_build_deployment_request_binds_exact_release_identity() -> None:
    request = build_deployment_request(
        repository="owner/Hamoon",
        manifest=_manifest(),
        admission=_admission(),
    )

    assert request["commit_sha"] == COMMIT
    assert request["release_artifact_name"] == f"hamoon-release-{COMMIT}"
    assert request["deployment_id"] == "prod-20261005-001"
    backend = cast(dict[str, object], request["backend"])
    frontend = cast(dict[str, object], request["frontend"])
    assert backend["image_id"] == API_IMAGE_ID
    assert frontend["image_id"] == WEB_IMAGE_ID


def test_execute_production_deployment_accepts_bound_final_receipt() -> None:
    observed_authorization: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_authorization.append(request.headers["Authorization"])
        return httpx.Response(200, json=_receipt())

    request_payload, receipt = execute_production_deployment(
        orchestrator_endpoint="https://deploy.example.com/v1/deployments",
        token=TOKEN,
        repository="owner/Hamoon",
        manifest=_manifest(),
        admission=_admission(),
        transport=httpx.MockTransport(handler),
    )

    assert request_payload["commit_sha"] == COMMIT
    assert receipt["status"] == "DEPLOYED"
    assert observed_authorization == [f"Bearer {TOKEN}"]


def test_execute_production_deployment_polls_same_host_until_deployed() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.method == "POST":
            return httpx.Response(
                202,
                json={
                    "status": "ACCEPTED",
                    "status_url": "https://deploy.example.com/v1/deployments/receipt-001",
                },
            )
        return httpx.Response(200, json=_receipt())

    _, receipt = execute_production_deployment(
        orchestrator_endpoint="https://deploy.example.com/v1/deployments",
        token=TOKEN,
        repository="owner/Hamoon",
        manifest=_manifest(),
        admission=_admission(),
        max_wait_seconds=1,
        poll_interval_seconds=0.001,
        transport=httpx.MockTransport(handler),
    )

    assert receipt["receipt_id"] == "receipt-001"
    assert calls == [
        "https://deploy.example.com/v1/deployments",
        "https://deploy.example.com/v1/deployments/receipt-001",
    ]


def test_execute_production_deployment_rejects_cross_host_status_url() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            202,
            json={
                "status": "ACCEPTED",
                "status_url": "https://evil.example.net/status/1",
            },
        )

    with pytest.raises(
        DeploymentOrchestratorError,
        match="must remain on the orchestrator HTTPS origin",
    ):
        execute_production_deployment(
            orchestrator_endpoint="https://deploy.example.com/v1/deployments",
            token=TOKEN,
            repository="owner/Hamoon",
            manifest=_manifest(),
            admission=_admission(),
            transport=httpx.MockTransport(handler),
        )


def test_execute_production_deployment_rejects_local_orchestrator() -> None:
    with pytest.raises(
        DeploymentOrchestratorError,
        match="must be remote HTTPS",
    ):
        execute_production_deployment(
            orchestrator_endpoint="https://localhost/deploy",
            token=TOKEN,
            repository="owner/Hamoon",
            manifest=_manifest(),
            admission=_admission(),
        )


def test_build_deployment_request_rejects_image_drift() -> None:
    admission = _admission()
    admission["backend_image_id"] = "sha256:" + "9" * 64

    with pytest.raises(
        DeploymentOrchestratorError,
        match="Backend image identity",
    ):
        build_deployment_request(
            repository="owner/Hamoon",
            manifest=_manifest(),
            admission=admission,
        )



def test_execute_production_deployment_rejects_cross_port_status_url() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            202,
            json={
                "status": "ACCEPTED",
                "status_url": "https://deploy.example.com:8443/status/1",
            },
        )

    with pytest.raises(
        DeploymentOrchestratorError,
        match="must remain on the orchestrator HTTPS origin",
    ):
        execute_production_deployment(
            orchestrator_endpoint="https://deploy.example.com/v1/deployments",
            token=TOKEN,
            repository="owner/Hamoon",
            manifest=_manifest(),
            admission=_admission(),
            transport=httpx.MockTransport(handler),
        )



def test_build_preflight_request_binds_runtime_contract() -> None:
    request = build_preflight_request(
        repository="owner/Hamoon",
        manifest=_manifest(),
        admission=_admission(),
        requirements=_requirements(),
        requirements_sha256="2" * 64,
    )

    assert request["operation"] == "PREFLIGHT_HAMOON_PRODUCTION"
    metadata = cast(dict[str, object], request["runtime_preflight"])
    assert metadata["contract_sha256"] == "2" * 64
    assert metadata["required_checks"] == PREFLIGHT_CHECKS


def test_execute_production_preflight_requires_all_checks_ready() -> None:
    observed_operations: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_operations.append(request.json()["operation"])
        return httpx.Response(200, json=_preflight_receipt())

    request_payload, receipt = execute_production_preflight(
        orchestrator_endpoint="https://deploy.example.com/v1/deployments",
        token=TOKEN,
        repository="owner/Hamoon",
        manifest=_manifest(),
        admission=_admission(),
        requirements=_requirements(),
        requirements_sha256="2" * 64,
        transport=httpx.MockTransport(handler),
    )

    assert request_payload["operation"] == "PREFLIGHT_HAMOON_PRODUCTION"
    assert receipt["status"] == "READY"
    assert observed_operations == ["PREFLIGHT_HAMOON_PRODUCTION"]


def test_execute_production_preflight_rejects_failed_required_check() -> None:
    receipt = _preflight_receipt()
    checks = cast(dict[str, object], receipt["checks"])
    checks["temporal_connectivity"] = False

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=receipt)

    with pytest.raises(
        DeploymentOrchestratorError,
        match="receipt check set does not match contract",
    ):
        execute_production_preflight(
            orchestrator_endpoint="https://deploy.example.com/v1/deployments",
            token=TOKEN,
            repository="owner/Hamoon",
            manifest=_manifest(),
            admission=_admission(),
            requirements=_requirements(),
            requirements_sha256="2" * 64,
            transport=httpx.MockTransport(handler),
        )


def test_execute_production_preflight_rejects_false_required_check() -> None:
    receipt = _preflight_receipt()
    checks = cast(dict[str, object], receipt["checks"])
    checks["postgresql_connectivity"] = False

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=receipt)

    with pytest.raises(
        DeploymentOrchestratorError,
        match="failed required checks: postgresql_connectivity",
    ):
        execute_production_preflight(
            orchestrator_endpoint="https://deploy.example.com/v1/deployments",
            token=TOKEN,
            repository="owner/Hamoon",
            manifest=_manifest(),
            admission=_admission(),
            requirements=_requirements(),
            requirements_sha256="2" * 64,
            transport=httpx.MockTransport(handler),
        )
