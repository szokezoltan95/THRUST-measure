"""Validation, summary metrics and normalized SCoPE step-response curves."""

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
RESPONSE_BY_REQUEST = {
    "AREQ": "AILE",
    "EREQ": "ELEV",
    "TREQ": "THRO",
    "RREQ": "RUDD",
}
RESPONSE_NAMES = tuple(RESPONSE_BY_REQUEST.values())


class ScopeLogError(ValueError):
    """Raised when a SCoPE log does not match the expected contract."""


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _normalized_channel_curve(
    rows: list[dict[str, float]],
    request_name: str,
    response_name: str,
    horizon_samples: int,
) -> dict[str, list[float]]:
    transitions = [
        index
        for index in range(1, len(rows))
        if rows[index][request_name] != rows[index - 1][request_name]
    ]
    segments: list[list[float]] = []
    for index in transitions:
        amplitude = rows[index][request_name] - rows[index - 1][request_name]
        if amplitude == 0:
            continue
        baseline = rows[index - 1][response_name]
        segment = [
            (rows[position][response_name] - baseline) / amplitude
            for position in range(index, min(len(rows), index + horizon_samples))
        ]
        if len(segment) >= 3:
            segments.append(segment)

    mean_curve: list[float] = []
    median_curve: list[float] = []
    std_curve: list[float] = []
    for sample in range(horizon_samples):
        values = [segment[sample] for segment in segments if sample < len(segment)]
        if not values:
            break
        mean = sum(values) / len(values)
        mean_curve.append(mean)
        median_curve.append(_median(values))
        std_curve.append(math.sqrt(sum((value - mean) ** 2 for value in values) / len(values)))

    return {
        "mean": mean_curve,
        "median": median_curve,
        "std": std_curve,
        "transition_count": [float(len(segments))],
    }


def build_normalized_step_response(
    rows: list[dict[str, float]],
    sampling_hz: float,
    *,
    horizon_s: float = 2.0,
) -> dict[str, Any]:
    """Align response to request transitions and normalize each step to unit amplitude."""
    horizon_samples = max(10, min(240, round(sampling_hz * horizon_s)))
    channels = {
        response_name: _normalized_channel_curve(
            rows, request_name, response_name, horizon_samples
        )
        for request_name, response_name in RESPONSE_BY_REQUEST.items()
    }
    longest = max((len(curve["mean"]) for curve in channels.values()), default=0)
    return {
        "schema_version": "scope-normalized-response-v1",
        "horizon_s": horizon_s,
        "sampling_hz": sampling_hz,
        "time_s": [index / sampling_hz for index in range(longest)],
        "channels": channels,
    }


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

    sampling_hz = (len(rows) - 1) / duration
    channel_summaries: dict[str, dict[str, float]] = {}
    for channel in (*RESPONSE_NAMES, *REQUEST_COLUMNS):
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
        "schema_version": "scope-analysis-v2",
        "source_format": "SCoPE_TSV_V1",
        "source_file": source.name,
        "sample_count": len(rows),
        "start_time_s": times[0],
        "end_time_s": times[-1],
        "duration_s": duration,
        "estimated_sampling_hz": sampling_hz,
        "columns": sorted(columns),
        "request_transition_count": transitions,
        "channels": channel_summaries,
        "normalized_step_response": build_normalized_step_response(rows, sampling_hz),
    }
