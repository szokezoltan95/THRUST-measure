from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def analysis_sidecar_path(raw_log: str | Path) -> Path:
    path = Path(raw_log)
    if path.suffix == ".gz":
        path = path.with_suffix("")
    return path.with_suffix(".analysis.json")


def build_analysis_artifact(
    raw_log: str | Path,
    analysis: dict[str, Any],
    *,
    started_at: str,
    test: dict[str, Any],
    parameters: dict[str, Any],
    runtime: dict[str, Any],
    session_summary: dict[str, Any] | None = None,
    raw_bytes: bytes | None = None,
    raw_file_name: str | None = None,
) -> dict[str, Any]:
    raw_path = Path(raw_log)
    raw_bytes = raw_bytes if raw_bytes is not None else raw_path.read_bytes()
    artifact = dict(analysis)
    artifact.update({
        "schema_version": "thrust-analysis-v1",
        "started_at": started_at,
        "producer": {"application": "THRUST-measure", "version": "0.1.0"},
        "raw_log": {
            "file_name": raw_file_name or raw_path.name,
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "size_bytes": len(raw_bytes),
            "content_type": (
                "application/gzip"
                if (raw_file_name or raw_path.name).endswith(".gz")
                else "text/tab-separated-values"
            ),
        },
        "test": {
            "test_code": str(test.get("test_code", "LOCAL")),
            "version": str(test.get("version", "local")),
        },
        "parameters": parameters,
        "runtime": {
            key: runtime[key]
            for key in ("axis_map", "deadzone", "break_axis", "reset_axis", "joystick_name")
            if key in runtime
        },
        "session_summary": session_summary or {},
    })
    return artifact


def save_analysis_artifact(raw_log: str | Path, artifact: dict[str, Any]) -> Path:
    target = analysis_sidecar_path(raw_log)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(artifact, ensure_ascii=False, allow_nan=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target
