from __future__ import annotations

import time
from datetime import datetime
from typing import cast
from urllib.parse import urlsplit

import httpx


class DeploymentOrchestratorError(RuntimeError):
    """Raised when a production deployment orchestrator cannot be trusted."""


def _remote_https_endpoint(value: str, *, expected_host: str | None = None) -> str:
    endpoint = value.strip()
    parsed = urlsplit(endpoint)
    host = parsed.hostname.lower() if parsed.hostname is not None else None
    if (
        parsed.scheme != "https"
        or host is None
        or host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "::"}
        or host.endswith(".localhost")
    ):
        raise DeploymentOrchestratorError(
            "Deployment orchestrator endpoint must be remote HTTPS."
        )
    if expected_host is not None and host != expected_host:
        raise DeploymentOrchestratorError(
            "Deployment status URL must remain on the orchestrator host."
        )
    return endpoint


def _require_string(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeploymentOrchestratorError(f"{field} is required.")
    return value.strip()


def build_deployment_request(
    *,
    repository: str,
    manifest: dict[str, object],
    admission: dict[str, object],
) -> dict[str, object]:
    commit_sha = _require_string(admission.get("commit_sha"), field="commit_sha")
    source_ci_run_id = _require_string(
        admission.get("source_ci_run_id"),
        field="source_ci_run_id",
    )
    backend_value = manifest.get("backend")
    frontend_value = manifest.get("frontend")
    if not isinstance(backend_value, dict) or not isinstance(frontend_value, dict):
        raise DeploymentOrchestratorError("Release manifest image metadata is missing.")
    backend = cast(dict[str, object], backend_value)
    frontend = cast(dict[str, object], frontend_value)

    manifest_commit = _require_string(
        manifest.get("commit_sha"),
        field="manifest.commit_sha",
    )
    manifest_run_id = _require_string(
        manifest.get("workflow_run_id"),
        field="manifest.workflow_run_id",
    )
    if manifest_commit != commit_sha:
        raise DeploymentOrchestratorError("Release manifest commit does not match admission.")
    if manifest_run_id != source_ci_run_id:
        raise DeploymentOrchestratorError("Release manifest run does not match admission.")

    backend_image_id = _require_string(
        backend.get("image_id"),
        field="backend.image_id",
    )
    frontend_image_id = _require_string(
        frontend.get("image_id"),
        field="frontend.image_id",
    )
    if backend_image_id != admission.get("backend_image_id"):
        raise DeploymentOrchestratorError("Backend image identity does not match admission.")
    if frontend_image_id != admission.get("frontend_image_id"):
        raise DeploymentOrchestratorError("Frontend image identity does not match admission.")

    return {
        "schema_version": 1,
        "operation": "DEPLOY_HAMOON_RELEASE",
        "repository": repository,
        "release_artifact_name": f"hamoon-release-{commit_sha}",
        "commit_sha": commit_sha,
        "source_ci_run_id": source_ci_run_id,
        "production_target": _require_string(
            admission.get("production_target"),
            field="production_target",
        ),
        "production_endpoint": _remote_https_endpoint(
            _require_string(
                admission.get("production_endpoint"),
                field="production_endpoint",
            )
        ),
        "deployment_id": _require_string(
            admission.get("expected_deployment_id"),
            field="expected_deployment_id",
        ),
        "backend": {
            "image_id": backend_image_id,
            "archive": _require_string(
                backend.get("archive"),
                field="backend.archive",
            ),
            "archive_sha256": _require_string(
                backend.get("archive_sha256"),
                field="backend.archive_sha256",
            ),
        },
        "frontend": {
            "image_id": frontend_image_id,
            "archive": _require_string(
                frontend.get("archive"),
                field="frontend.archive",
            ),
            "archive_sha256": _require_string(
                frontend.get("archive_sha256"),
                field="frontend.archive_sha256",
            ),
        },
        "governance": {
            "release_approval_run_id": _require_string(
                admission.get("release_approval_run_id"),
                field="release_approval_run_id",
            ),
            "deployment_admission_run_id": _require_string(
                admission.get("deployment_admission_run_id"),
                field="deployment_admission_run_id",
            ),
            "release_manifest_sha256": _require_string(
                admission.get("release_manifest_sha256"),
                field="release_manifest_sha256",
            ),
            "release_approval_sha256": _require_string(
                admission.get("release_approval_sha256"),
                field="release_approval_sha256",
            ),
        },
    }


def _response_json(response: httpx.Response) -> dict[str, object]:
    if response.status_code not in {200, 201, 202}:
        raise DeploymentOrchestratorError(
            f"Deployment orchestrator returned HTTP {response.status_code}."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise DeploymentOrchestratorError(
            "Deployment orchestrator returned invalid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise DeploymentOrchestratorError(
            "Deployment orchestrator response must be a JSON object."
        )
    return cast(dict[str, object], payload)


def _validate_final_receipt(
    *,
    receipt: dict[str, object],
    request: dict[str, object],
) -> dict[str, object]:
    if receipt.get("status") != "DEPLOYED":
        raise DeploymentOrchestratorError("Deployment did not reach DEPLOYED state.")

    expected = {
        "commit_sha": request["commit_sha"],
        "deployment_id": request["deployment_id"],
        "production_target": request["production_target"],
        "production_endpoint": request["production_endpoint"],
        "backend_image_id": cast(dict[str, object], request["backend"])["image_id"],
        "frontend_image_id": cast(dict[str, object], request["frontend"])["image_id"],
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise DeploymentOrchestratorError(
                f"Deployment receipt {field} does not match requested release."
            )

    receipt_id = _require_string(receipt.get("receipt_id"), field="receipt_id")
    if len(receipt_id) > 200:
        raise DeploymentOrchestratorError("receipt_id is too long.")

    deployed_at = _require_string(receipt.get("deployed_at"), field="deployed_at")
    try:
        timestamp = datetime.fromisoformat(deployed_at)
    except ValueError as exc:
        raise DeploymentOrchestratorError("deployed_at is invalid.") from exc
    if timestamp.tzinfo is None:
        raise DeploymentOrchestratorError("deployed_at must include a timezone.")

    return dict(receipt)


def execute_production_deployment(
    *,
    orchestrator_endpoint: str,
    token: str,
    repository: str,
    manifest: dict[str, object],
    admission: dict[str, object],
    timeout_seconds: float = 30.0,
    max_wait_seconds: float = 600.0,
    poll_interval_seconds: float = 5.0,
    transport: httpx.BaseTransport | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    endpoint = _remote_https_endpoint(orchestrator_endpoint)
    orchestrator_host = urlsplit(endpoint).hostname
    assert orchestrator_host is not None

    secret = token.strip()
    if len(secret) < 32:
        raise DeploymentOrchestratorError(
            "Deployment orchestrator token must contain at least 32 characters."
        )
    if timeout_seconds <= 0 or max_wait_seconds <= 0 or poll_interval_seconds <= 0:
        raise DeploymentOrchestratorError("Deployment timing values must be positive.")

    request_payload = build_deployment_request(
        repository=repository,
        manifest=manifest,
        admission=admission,
    )
    headers = {
        "Authorization": f"Bearer {secret}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "hamoon-production-deployer/1",
    }

    with httpx.Client(
        timeout=timeout_seconds,
        follow_redirects=False,
        transport=transport,
        headers=headers,
    ) as client:
        response = client.post(endpoint, json=request_payload)
        current = _response_json(response)

        status = current.get("status")
        if status == "DEPLOYED":
            return request_payload, _validate_final_receipt(
                receipt=current,
                request=request_payload,
            )
        if status not in {"ACCEPTED", "IN_PROGRESS"}:
            raise DeploymentOrchestratorError(
                "Deployment orchestrator did not accept the deployment."
            )

        status_url = _remote_https_endpoint(
            _require_string(current.get("status_url"), field="status_url"),
            expected_host=orchestrator_host.lower(),
        )
        deadline = time.monotonic() + max_wait_seconds

        while time.monotonic() < deadline:
            time.sleep(poll_interval_seconds)
            current = _response_json(client.get(status_url))
            status = current.get("status")
            if status == "DEPLOYED":
                return request_payload, _validate_final_receipt(
                    receipt=current,
                    request=request_payload,
                )
            if status == "FAILED":
                raise DeploymentOrchestratorError(
                    "Deployment orchestrator reported FAILED state."
                )
            if status not in {"ACCEPTED", "IN_PROGRESS"}:
                raise DeploymentOrchestratorError(
                    "Deployment orchestrator returned an unknown state."
                )

    raise DeploymentOrchestratorError("Production deployment timed out.")
