"""Robust SCoPE log validation and step-response analysis.

The local client performs the computationally sensitive work. Each request
transition is analysed independently, then curves and robust metrics are
exported for the WebDB.
"""
from __future__ import annotations

import csv
import gzip
import math
from pathlib import Path
from statistics import median
from typing import Any

REQUIRED_COLUMNS = {"TIME", "AILE", "ELEV", "THRO", "RUDD", "AREQ", "EREQ", "TREQ", "RREQ"}
REQUEST_COLUMNS = ("AREQ", "EREQ", "TREQ", "RREQ")
RESPONSE_BY_REQUEST = {"AREQ": "AILE", "EREQ": "ELEV", "TREQ": "THRO", "RREQ": "RUDD"}
RESPONSE_NAMES = tuple(RESPONSE_BY_REQUEST.values())


class ScopeLogError(ValueError):
    """Raised when a SCoPE log does not match the expected contract."""


def _finite(values: list[float]) -> list[float]:
    return [value for value in values if math.isfinite(value)]


def _percentile(values: list[float], fraction: float) -> float | None:
    values = sorted(_finite(values))
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    position = fraction * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def _crossing_time(time: list[float], values: list[float], level: float) -> float | None:
    for index in range(1, min(len(time), len(values))):
        previous = values[index - 1]
        current = values[index]
        if previous < level <= current:
            difference = current - previous
            fraction = (level - previous) / difference if difference else 0.0
            return time[index - 1] + fraction * (time[index] - time[index - 1])
    return None


def _step_metrics(time: list[float], curve: list[float], std: list[float]) -> dict[str, float | None]:
    count = min(len(time), len(curve))
    empty = {
        "reaction_delay_s": None, "rise_time_s": None, "overshoot_pct": None,
        "settling_time_s": None, "steady_state_error_pct": None,
        "tracking_rmse": None, "mean_std": None,
    }
    if count < 3:
        return empty
    time = time[:count]
    curve = [float(value) for value in curve[:count]]
    t10 = _crossing_time(time, curve, 0.1)
    t90 = _crossing_time(time, curve, 0.9)
    peak = max(curve)
    final_window = max(1, count // 10)
    final_value = sum(curve[-final_window:]) / final_window
    last_outside = -1
    for index, value in enumerate(curve):
        if abs(value - 1.0) > 0.05:
            last_outside = index
    settling = time[last_outside] if 0 <= last_outside < count - 1 else None
    rmse_start = next((index for index, value in enumerate(curve) if value >= 0.1), 0)
    rmse = math.sqrt(sum((value - 1.0) ** 2 for value in curve[rmse_start:]) / max(1, count - rmse_start))
    std_values = _finite(std[:count])
    return {
        "reaction_delay_s": t10,
        "rise_time_s": max(0.0, t90 - t10) if t10 is not None and t90 is not None else None,
        "overshoot_pct": max(0.0, (peak - 1.0) * 100.0),
        "settling_time_s": settling,
        "steady_state_error_pct": abs(1.0 - final_value) * 100.0,
        "tracking_rmse": rmse,
        "mean_std": sum(std_values) / len(std_values) if std_values else None,
    }


def _aggregate_step_metrics(metrics: list[dict[str, float | None]]) -> dict[str, Any]:
    result: dict[str, Any] = {"aggregation": "median", "step_count": len(metrics)}
    for name in (
        "reaction_delay_s", "rise_time_s", "overshoot_pct", "settling_time_s",
        "steady_state_error_pct", "tracking_rmse", "mean_std",
    ):
        values = [float(item[name]) for item in metrics if item.get(name) is not None]
        result[name] = _percentile(values, 0.5)
        result[f"{name}_mean"] = sum(values) / len(values) if values else None
    return result


def _normalized_channel_curve(
    rows: list[dict[str, float]],
    request_name: str,
    response_name: str,
    sampling_hz: float,
    horizon_samples: int,
    *,
    min_step_amplitude: float,
) -> dict[str, Any]:
    transitions = [
        index for index in range(1, len(rows))
        if abs(rows[index][request_name] - rows[index - 1][request_name]) >= min_step_amplitude
    ]
    pre_samples = max(3, round(sampling_hz * 0.10))
    segments: list[list[float]] = []
    metric_rows: list[dict[str, float | None]] = []
    for transition_number, index in enumerate(transitions):
        request_delta = rows[index][request_name] - rows[index - 1][request_name]
        baseline_values = [
            rows[position][response_name]
            for position in range(max(0, index - pre_samples), index)
        ]
        if len(baseline_values) < 3 or request_delta == 0:
            continue
        baseline = median(baseline_values)
        next_transition = (
            transitions[transition_number + 1]
            if transition_number + 1 < len(transitions)
            else len(rows)
        )
        end = min(len(rows), index + horizon_samples, next_transition)
        segment = [
            (rows[position][response_name] - baseline) / request_delta
            for position in range(index, end)
        ]
        if len(segment) < 3:
            continue
        segment_time = [
            rows[position]["TIME"] - rows[index]["TIME"]
            for position in range(index, end)
        ]
        segments.append(segment)
        metric_rows.append(_step_metrics(segment_time, segment, []))
    mean_curve: list[float] = []
    median_curve: list[float] = []
    std_curve: list[float] = []
    for sample in range(horizon_samples):
        values = [segment[sample] for segment in segments if sample < len(segment)]
        if not values:
            break
        average = sum(values) / len(values)
        mean_curve.append(average)
        median_curve.append(median(values))
        std_curve.append(math.sqrt(sum((value - average) ** 2 for value in values) / len(values)))
    curve_time = [index / sampling_hz for index in range(len(mean_curve))]
    aggregate = _aggregate_step_metrics(metric_rows)
    if std_curve:
        aggregate["mean_std"] = sum(std_curve) / len(std_curve)
        aggregate["mean_std_mean"] = aggregate["mean_std"]
    return {
        "mean": mean_curve,
        "median": median_curve,
        "std": std_curve,
        "time_s": curve_time,
        "transition_count": len(segments),
        "metrics": aggregate,
    }


def build_normalized_step_response(
    rows: list[dict[str, float]],
    sampling_hz: float,
    *,
    horizon_s: float = 1.5,
    min_step_amplitude: float = 100.0,
) -> dict[str, Any]:
    horizon_samples = max(10, min(300, round(sampling_hz * horizon_s) + 1))
    channels = {
        response_name: _normalized_channel_curve(
            rows, request_name, response_name, sampling_hz, horizon_samples,
            min_step_amplitude=min_step_amplitude,
        )
        for request_name, response_name in RESPONSE_BY_REQUEST.items()
    }
    longest = max((len(curve["mean"]) for curve in channels.values()), default=0)
    return {
        "schema_version": "scope-normalized-response-v2",
        "horizon_s": horizon_s,
        "min_step_amplitude": min_step_amplitude,
        "sampling_hz": sampling_hz,
        "time_s": [index / sampling_hz for index in range(longest)],
        "channels": channels,
    }


def analyze_scope_log(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise ScopeLogError(f"SCoPE log does not exist: {source}")
    opener = gzip.open if source.suffix == ".gz" else open
    with opener(source, "rt", encoding="utf-8", newline="") as handle:
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
    intervals = [current - previous for previous, current in zip(times, times[1:])]
    if any(interval <= 0 for interval in intervals):
        raise ScopeLogError("SCoPE TIME column must be strictly increasing.")
    sampling_hz = 1.0 / median(intervals)
    duration = times[-1] - times[0]
    channel_summaries: dict[str, dict[str, float]] = {}
    for channel in (*RESPONSE_NAMES, *REQUEST_COLUMNS):
        values = [row[channel] for row in rows]
        channel_summaries[channel] = {
            "min": min(values), "max": max(values),
            "mean": sum(values) / len(values),
            "rms": math.sqrt(sum(value * value for value in values) / len(values)),
        }
    transitions = {
        channel: sum(
            1 for previous, current in zip(rows, rows[1:])
            if current[channel] != previous[channel]
        )
        for channel in REQUEST_COLUMNS
    }
    return {
        "schema_version": "scope-analysis-v3",
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
