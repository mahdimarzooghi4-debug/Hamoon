#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"release bundle invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"release bundle invalid: cannot parse {path.name}: {exc}") from exc
    require(isinstance(value, dict), f"{path.name} must contain a JSON object")
    return value


def verify_component(root: Path, name: str, component: object) -> None:
    require(isinstance(component, dict), f"{name} metadata must be an object")
    image = component.get("image")
    image_id = component.get("image_id")
    archive = component.get("archive")
    archive_sha256 = component.get("archive_sha256")
    sbom = component.get("sbom")
    sbom_sha256 = component.get("sbom_sha256")

    require(isinstance(image, str) and image, f"{name}.image missing")
    require(
        isinstance(image_id, str) and IMAGE_ID_RE.fullmatch(image_id) is not None,
        f"{name}.image_id invalid",
    )
    require(isinstance(archive, str) and archive, f"{name}.archive missing")
    require(
        isinstance(archive_sha256, str)
        and SHA256_RE.fullmatch(archive_sha256) is not None,
        f"{name}.archive_sha256 invalid",
    )
    require(isinstance(sbom, str) and sbom, f"{name}.sbom missing")
    require(
        isinstance(sbom_sha256, str)
        and SHA256_RE.fullmatch(sbom_sha256) is not None,
        f"{name}.sbom_sha256 invalid",
    )

    archive_path = root / archive
    sbom_path = root / sbom
    require(archive_path.is_file(), f"missing {archive}")
    require(sbom_path.is_file(), f"missing {sbom}")
    require(
        sha256_file(archive_path) == archive_sha256,
        f"{archive} SHA-256 mismatch",
    )
    require(
        sha256_file(sbom_path) == sbom_sha256,
        f"{sbom} SHA-256 mismatch",
    )

    sbom_json = load_json(sbom_path)
    require(sbom_json.get("bomFormat") == "CycloneDX", f"{sbom} is not CycloneDX")
    require(
        isinstance(sbom_json.get("components"), list),
        f"{sbom} has no components inventory",
    )


def main() -> None:
    require(len(sys.argv) == 2, "usage: verify_release_bundle.py <release-dir>")
    root = Path(sys.argv[1]).resolve()
    manifest = load_json(root / "manifest.json")

    require(manifest.get("schema_version") == 2, "unsupported manifest schema")
    repository = manifest.get("repository")
    commit_sha = manifest.get("commit_sha")
    workflow_run_id = manifest.get("workflow_run_id")
    require(isinstance(repository, str) and "/" in repository, "repository invalid")
    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "commit_sha invalid",
    )
    require(
        isinstance(workflow_run_id, str) and workflow_run_id.isdigit(),
        "workflow_run_id invalid",
    )

    verify_component(root, "backend", manifest.get("backend"))
    verify_component(root, "frontend", manifest.get("frontend"))

    provenance_name = manifest.get("provenance")
    provenance_sha256 = manifest.get("provenance_sha256")
    require(
        isinstance(provenance_name, str) and provenance_name,
        "provenance missing",
    )
    require(
        isinstance(provenance_sha256, str)
        and SHA256_RE.fullmatch(provenance_sha256) is not None,
        "provenance_sha256 invalid",
    )
    provenance_path = root / provenance_name
    require(provenance_path.is_file(), f"missing {provenance_name}")
    require(
        sha256_file(provenance_path) == provenance_sha256,
        "provenance SHA-256 mismatch",
    )

    provenance = load_json(provenance_path)
    require(
        provenance.get("_type") == "https://in-toto.io/Statement/v1",
        "provenance statement type invalid",
    )
    require(
        provenance.get("predicateType") == "https://slsa.dev/provenance/v1",
        "provenance predicate type invalid",
    )

    predicate = provenance.get("predicate")
    require(isinstance(predicate, dict), "provenance predicate missing")
    build_definition = predicate.get("buildDefinition")
    require(isinstance(build_definition, dict), "buildDefinition missing")
    external_parameters = build_definition.get("externalParameters")
    require(isinstance(external_parameters, dict), "externalParameters missing")
    require(
        external_parameters.get("repository") == repository,
        "provenance repository mismatch",
    )
    require(
        external_parameters.get("commit_sha") == commit_sha,
        "provenance commit mismatch",
    )

    subjects = provenance.get("subject")
    require(isinstance(subjects, list) and len(subjects) == 2, "subjects invalid")
    expected = {
        manifest["backend"]["archive"]: manifest["backend"]["archive_sha256"],
        manifest["frontend"]["archive"]: manifest["frontend"]["archive_sha256"],
    }
    actual: dict[str, str] = {}
    for subject in subjects:
        require(isinstance(subject, dict), "subject invalid")
        name = subject.get("name")
        digest = subject.get("digest")
        require(isinstance(name, str), "subject name invalid")
        require(isinstance(digest, dict), "subject digest invalid")
        value = digest.get("sha256")
        require(isinstance(value, str), "subject sha256 invalid")
        actual[name] = value
    require(actual == expected, "provenance subjects do not match release archives")

    checksums = root / "SHA256SUMS"
    require(checksums.is_file(), "SHA256SUMS missing")
    entries: dict[str, str] = {}
    for raw_line in checksums.read_text(encoding="utf-8").splitlines():
        digest, filename = raw_line.split(maxsplit=1)
        entries[Path(filename).name] = digest
    for filename in (
        "hamoon-api.tar",
        "hamoon-web.tar",
        "hamoon-api.cdx.json",
        "hamoon-web.cdx.json",
        "provenance.json",
    ):
        require(filename in entries, f"SHA256SUMS missing {filename}")
        require(
            sha256_file(root / filename) == entries[filename],
            f"SHA256SUMS mismatch for {filename}",
        )

    print(
        json.dumps(
            {
                "status": "valid",
                "repository": repository,
                "commit_sha": commit_sha,
                "workflow_run_id": workflow_run_id,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
