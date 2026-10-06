from __future__ import annotations

import time
from datetime import datetime
from typing import cast
from urllib.parse import urlsplit

import httpx


class DeploymentOrchestratorError(RuntimeError):
    """Raised when a production deployment orchestrator cannot be trusted."""


def _remote_https_endpoint(
    value: str,
    *,
    expected_host: str | None = None,
    expected_port: int | None = None,
) -> str:
    endpoint = value.strip()
    parsed = urlsplit(endpoint)
    host = parsed.hostname.lower() if parsed.hostname is not None else None
    if (
        parsed.scheme != "https"
        or host is None
        or host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "::"}
        or host.endswith(".localhost")
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise DeploymentOrchestratorError(
            "Deployment orchestrator endpoint must be remote HTTPS."
        )
    effective_port = parsed.port or 443
    if (
        expected_host is not None
        and (
            host != expected_host
            or (
                expected_port is not None
                and effective_port != expected_port
            )
        )
    ):
        raise DeploymentOrchestratorError(
            "Deployment status URL must remain on the orchestrator HTTPS origin."
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



def _internal_model_checkpoint_contract(
    requirements: dict[str, object],
) -> dict[str, object]:
    raw = requirements.get("internal_model_checkpoint")
    if not isinstance(raw, dict):
        raise DeploymentOrchestratorError(
            "Production internal model checkpoint contract is missing."
        )
    checkpoint = cast(dict[str, object], raw)
    required_fields = {
        "model_id",
        "revision",
        "model_sha256",
        "tokenizer_sha256",
        "execution_mode",
        "network_model_download",
    }
    if set(checkpoint) != required_fields:
        raise DeploymentOrchestratorError(
            "Production internal model checkpoint contract fields are invalid."
        )
    for field in ("model_id", "revision", "model_sha256", "tokenizer_sha256", "execution_mode"):
        value = checkpoint.get(field)
        if not isinstance(value, str) or not value.strip():
            raise DeploymentOrchestratorError(
                f"Production internal model checkpoint {field} is invalid."
            )
    for field in ("model_sha256", "tokenizer_sha256"):
        digest = cast(str, checkpoint[field])
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise DeploymentOrchestratorError(
                f"Production internal model checkpoint {field} is invalid."
            )
    if checkpoint.get("execution_mode") != "IN_PROCESS":
        raise DeploymentOrchestratorError(
            "Production internal model checkpoint execution_mode must be IN_PROCESS."
        )
    if checkpoint.get("network_model_download") is not False:
        raise DeploymentOrchestratorError(
            "Production internal model checkpoint network download must be disabled."
        )
    return dict(checkpoint)


def _required_preflight_checks(
    requirements: dict[str, object],
) -> tuple[str, ...]:
    if requirements.get("schema_version") != 2:
        raise DeploymentOrchestratorError(
            "Production runtime preflight schema_version is unsupported."
        )
    if requirements.get("contract") != "HAMOON_PRODUCTION_RUNTIME_PREFLIGHT":
        raise DeploymentOrchestratorError(
            "Production runtime preflight contract is invalid."
        )
    raw_checks = requirements.get("required_checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        raise DeploymentOrchestratorError(
            "Production runtime preflight required_checks are missing."
        )

    checks: list[str] = []
    for value in cast(list[object], raw_checks):
        if not isinstance(value, str) or not value.strip():
            raise DeploymentOrchestratorError(
                "Production runtime preflight check name is invalid."
            )
        check = value.strip()
        if check in checks:
            raise DeploymentOrchestratorError(
                "Production runtime preflight checks must be unique."
            )
        checks.append(check)
    return tuple(checks)


def build_preflight_request(
    *,
    repository: str,
    manifest: dict[str, object],
    admission: dict[str, object],
    requirements: dict[str, object],
    requirements_sha256: str,
) -> dict[str, object]:
    base = build_deployment_request(
        repository=repository,
        manifest=manifest,
        admission=admission,
    )
    checks = _required_preflight_checks(requirements)
    checkpoint = _internal_model_checkpoint_contract(requirements)
    if len(requirements_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in requirements_sha256
    ):
        raise DeploymentOrchestratorError(
            "Production runtime preflight SHA-256 is invalid."
        )
    return {
        **base,
        "operation": "PREFLIGHT_HAMOON_PRODUCTION",
        "runtime_preflight": {
            "contract_sha256": requirements_sha256,
            "required_checks": list(checks),
            "internal_model_checkpoint": checkpoint,
        },
    }


def _validate_preflight_receipt(
    *,
    receipt: dict[str, object],
    request: dict[str, object],
) -> dict[str, object]:
    if receipt.get("status") != "READY":
        raise DeploymentOrchestratorError(
            "Production runtime preflight did not reach READY state."
        )

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
                f"Preflight receipt {field} does not match requested release."
            )

    preflight_id = _require_string(
        receipt.get("preflight_id"),
        field="preflight_id",
    )
    if len(preflight_id) > 200:
        raise DeploymentOrchestratorError("preflight_id is too long.")

    checked_at = _require_string(receipt.get("checked_at"), field="checked_at")
    try:
        timestamp = datetime.fromisoformat(checked_at)
    except ValueError as exc:
        raise DeploymentOrchestratorError("checked_at is invalid.") from exc
    if timestamp.tzinfo is None:
        raise DeploymentOrchestratorError("checked_at must include a timezone.")

    runtime_preflight_value = request.get("runtime_preflight")
    if not isinstance(runtime_preflight_value, dict):
        raise DeploymentOrchestratorError(
            "Production runtime preflight request metadata is missing."
        )
    runtime_preflight = cast(dict[str, object], runtime_preflight_value)
    checkpoint_value = runtime_preflight.get("internal_model_checkpoint")
    if not isinstance(checkpoint_value, dict):
        raise DeploymentOrchestratorError(
            "Production internal model checkpoint request metadata is missing."
        )
    checkpoint = cast(dict[str, object], checkpoint_value)
    receipt_checkpoint = receipt.get("internal_model_checkpoint")
    if not isinstance(receipt_checkpoint, dict):
        raise DeploymentOrchestratorError(
            "Production internal model checkpoint attestation is missing."
        )
    if cast(dict[str, object], receipt_checkpoint) != checkpoint:
        raise DeploymentOrchestratorError(
            "Production internal model checkpoint attestation does not match request."
        )

    required_checks_value = runtime_preflight.get("required_checks")
    if not isinstance(required_checks_value, list):
        raise DeploymentOrchestratorError(
            "Production runtime preflight required checks are missing."
        )
    required_checks: list[str] = []
    for value in cast(list[object], required_checks_value):
        if not isinstance(value, str):
            raise DeploymentOrchestratorError(
                "Production runtime preflight required check is invalid."
            )
        required_checks.append(value)

    raw_checks = receipt.get("checks")
    if not isinstance(raw_checks, dict):
        raise DeploymentOrchestratorError(
            "Production runtime preflight checks are missing."
        )
    checks = cast(dict[str, object], raw_checks)
    if set(checks) != set(required_checks):
        raise DeploymentOrchestratorError(
            "Production runtime preflight receipt check set does not match contract."
        )
    failed = [
        check
        for check in required_checks
        if checks.get(check) is not True
    ]
    if failed:
        raise DeploymentOrchestratorError(
            "Production runtime preflight failed required checks: "
            + ",".join(failed)
        )

    return dict(receipt)

def execute_production_preflight(
    *,
    orchestrator_endpoint: str,
    token: str,
    repository: str,
    manifest: dict[str, object],
    admission: dict[str, object],
    requirements: dict[str, object],
    requirements_sha256: str,
    timeout_seconds: float = 30.0,
    max_wait_seconds: float = 300.0,
    poll_interval_seconds: float = 5.0,
    transport: httpx.BaseTransport | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    endpoint = _remote_https_endpoint(orchestrator_endpoint)
    orchestrator_parsed = urlsplit(endpoint)
    orchestrator_host = orchestrator_parsed.hostname
    assert orchestrator_host is not None
    orchestrator_port = orchestrator_parsed.port or 443

    secret = token.strip()
    if len(secret) < 32:
        raise DeploymentOrchestratorError(
            "Deployment orchestrator token must contain at least 32 characters."
        )
    if timeout_seconds <= 0 or max_wait_seconds <= 0 or poll_interval_seconds <= 0:
        raise DeploymentOrchestratorError("Preflight timing values must be positive.")

    request_payload = build_preflight_request(
        repository=repository,
        manifest=manifest,
        admission=admission,
        requirements=requirements,
        requirements_sha256=requirements_sha256,
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
        if status == "READY":
            return request_payload, _validate_preflight_receipt(
                receipt=current,
                request=request_payload,
            )
        if status not in {"ACCEPTED", "IN_PROGRESS"}:
            raise DeploymentOrchestratorError(
                "Deployment orchestrator did not accept Production preflight."
            )

        status_url = _remote_https_endpoint(
            _require_string(current.get("status_url"), field="status_url"),
            expected_host=orchestrator_host.lower(),
            expected_port=orchestrator_port,
        )
        deadline = time.monotonic() + max_wait_seconds

        while time.monotonic() < deadline:
            time.sleep(poll_interval_seconds)
            current = _response_json(client.get(status_url))
            status = current.get("status")
            if status == "READY":
                return request_payload, _validate_preflight_receipt(
                    receipt=current,
                    request=request_payload,
                )
            if status == "FAILED":
                raise DeploymentOrchestratorError(
                    "Production runtime preflight reported FAILED state."
                )
            if status not in {"ACCEPTED", "IN_PROGRESS"}:
                raise DeploymentOrchestratorError(
                    "Production runtime preflight returned an unknown state."
                )

    raise DeploymentOrchestratorError("Production runtime preflight timed out.")


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

    runtime_preflight_value = request.get("runtime_preflight")
    if not isinstance(runtime_preflight_value, dict):
        raise DeploymentOrchestratorError(
            "Deployment request runtime preflight binding is missing."
        )
    runtime_preflight = cast(dict[str, object], runtime_preflight_value)
    expected = {
        "commit_sha": request["commit_sha"],
        "deployment_id": request["deployment_id"],
        "production_target": request["production_target"],
        "production_endpoint": request["production_endpoint"],
        "backend_image_id": cast(dict[str, object], request["backend"])["image_id"],
        "frontend_image_id": cast(dict[str, object], request["frontend"])["image_id"],
        "preflight_id": _require_string(
            runtime_preflight.get("preflight_id"),
            field="runtime_preflight.preflight_id",
        ),
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
    preflight_receipt: dict[str, object],
    preflight_contract_sha256: str,
    timeout_seconds: float = 30.0,
    max_wait_seconds: float = 600.0,
    poll_interval_seconds: float = 5.0,
    transport: httpx.BaseTransport | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    endpoint = _remote_https_endpoint(orchestrator_endpoint)
    orchestrator_parsed = urlsplit(endpoint)
    orchestrator_host = orchestrator_parsed.hostname
    assert orchestrator_host is not None
    orchestrator_port = orchestrator_parsed.port or 443

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
    if preflight_receipt.get("status") != "READY":
        raise DeploymentOrchestratorError(
            "Production deployment requires a READY preflight receipt."
        )
    preflight_id = _require_string(
        preflight_receipt.get("preflight_id"),
        field="preflight_id",
    )
    if len(preflight_contract_sha256) != 64 or any(
        character not in "0123456789abcdef"
        for character in preflight_contract_sha256
    ):
        raise DeploymentOrchestratorError(
            "Production runtime preflight SHA-256 is invalid."
        )
    request_payload["runtime_preflight"] = {
        "preflight_id": preflight_id,
        "contract_sha256": preflight_contract_sha256,
    }
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
            expected_port=orchestrator_port,
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
