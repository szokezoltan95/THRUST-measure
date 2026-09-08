"""Local validation and basic metrics for SCoPE tab-separated logs."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {
    "TIME",
    "AILE",
    "ELEV",
    "THRO",
    "RUDD",
    "AREQ",
    "EREQ",
    "TREQ",
    "RREQ",
}
REQUEST_COLUMNS = ("AREQ", "EREQ", "TREQ", "RREQ")


class ScopeLogError(ValueError):
    """Raised when a SCoPE log does not match the expected contract."""


def analyze_scope_log(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise ScopeLogError(f"SCoPE log does not exist: {source}")

    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ScopeLogError(f"SCoPE log is missing columns: {sorted(missing)}")

        rows: list[dict[str, float]] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                rows.append({name: float(row[name]) for name in REQUIRED_COLUMNS})
            except (KeyError, TypeError, ValueError) as exc:
                raise ScopeLogError(f"Invalid numeric value on line {line_number}.") from exc

    if len(rows) < 2:
        raise ScopeLogError("SCoPE log must contain at least two samples.")

    times = [row["TIME"] for row in rows]
    duration = times[-1] - times[0]
    if duration <= 0:
        raise ScopeLogError("SCoPE TIME column must be strictly increasing.")

    channel_summaries: dict[str, dict[str, float]] = {}
    for channel in ("AILE", "ELEV", "THRO", "RUDD", *REQUEST_COLUMNS):
        values = [row[channel] for row in rows]
        channel_summaries[channel] = {
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "rms": math.sqrt(sum(value * value for value in values) / len(values)),
        }

    transitions = {
        channel: sum(
            1 for previous, current in zip(rows, rows[1:]) if current[channel] != previous[channel]
        )
        for channel in REQUEST_COLUMNS
    }

    return {
        "schema_version": "scope-analysis-v1",
        "source_format": "SCoPE_TSV_V1",
        "source_file": source.name,
        "sample_count": len(rows),
        "start_time_s": times[0],
        "end_time_s": times[-1],
        "duration_s": duration,
        "estimated_sampling_hz": (len(rows) - 1) / duration,
        "columns": sorted(columns),
        "request_transition_count": transitions,
        "channels": channel_summaries,
    }
