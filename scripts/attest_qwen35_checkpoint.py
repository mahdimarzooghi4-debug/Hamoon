#!/usr/bin/env python3
"""Create a deterministic Hamoon manifest for an already provisioned Qwen checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

MODEL_ID = "Qwen/Qwen3.5-9B"
BASELINE_REVISION = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
_META_FILES = {"hamoon-revision.txt", "hamoon-checkpoint-manifest.json"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-root", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    revision = args.revision.strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        parser.error("--revision must be a full 40-character commit SHA")
    if revision != BASELINE_REVISION:
        parser.error("--revision differs from the approved Qwen baseline")
    root = Path(args.checkpoint_root).resolve(strict=True)
    config_path = root / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("model_type") != "qwen3_5":
        parser.error("checkpoint config is not Qwen3.5")
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            parser.error(f"symlinks are not allowed in checkpoint: {path}")
        if path.is_file() and path.name not in _META_FILES:
            files[path.relative_to(root).as_posix()] = _sha256(path)
    if not files:
        parser.error("checkpoint contains no files")
    manifest = {
        "model_id": MODEL_ID,
        "revision": revision,
        "files": files,
    }
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    (root / "hamoon-revision.txt").write_text(revision + "\n", encoding="utf-8")
    (root / "hamoon-checkpoint-manifest.json").write_bytes(manifest_bytes)
    print(hashlib.sha256(manifest_bytes).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
