"""Dummy measurement runner using the bundled SCoPE fixture."""

from __future__ import annotations

import base64
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "assets" / "dummy_scope_log.gz.b64"


def run_dummy(
    *,
    participant_code: str,
    test_code: str,
    test_version: str,
    output_root: str,
    log_callback: Callable[[str], None] | None = None,
) -> Path:
    if not _FIXTURE_PATH.is_file():
        raise FileNotFoundError(f"Dummy fixture not found: {_FIXTURE_PATH}")

    timestamp = datetime.now(timezone.utc).astimezone()
    stamp = timestamp.strftime("%Y%m%d_%H%M%S")
    safe_participant = "".join(char for char in participant_code if char.isalnum()) or "DUMMY"
    safe_test = "".join(char if char.isalnum() or char in "-_" else "_" for char in test_code)
    output_dir = Path(output_root) / "dummy" / timestamp.strftime("%Y-%m-%d")
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_log = gzip.decompress(base64.b64decode(_FIXTURE_PATH.read_text(encoding="ascii")))
    raw_path = output_dir / f"SCoPE_dummy_{safe_participant}_{safe_test}_{stamp}.txt"
    raw_path.write_bytes(raw_log)

    metadata = {
        "source": "bundled_dummy_fixture",
        "fixture": _FIXTURE_PATH.name,
        "participant_code": participant_code,
        "test_code": test_code,
        "test_version": test_version,
        "started_at": timestamp.isoformat(),
        "row_format": "SCoPE tab-separated measurement log",
    }
    raw_path.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if log_callback:
        log_callback(f"Dummy fixture copied to: {raw_path}")
        log_callback("No joystick was accessed; this run is suitable for GUI and pipeline testing.")

    return raw_path
