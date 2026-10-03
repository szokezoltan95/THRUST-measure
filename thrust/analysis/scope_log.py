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

from thrust.analysis.response_metrics import estimate_response_onset, normalized_step_metrics

REQUIRED_COLUMNS = {"TIME", "LX", "LY", "RY", "RX", "LXRQ", "LYRQ", "RYRQ", "RXRQ"}
OPTIONAL_COLUMNS = {
    "ACTION_ID", "IN_RANGE", "LEVR", "BUTT", "SIDL", "SIDR",
    "LEFT_IN_ZONE", "RIGHT_IN_ZONE", "LEFT_SUCCESS", "RIGHT_SUCCESS",
    "TASK_SUCCESS", "TASK_LIMIT_S", "HOLD_REQUIRED_S", "TASK_ELAPSED_S", "TASK_RESULT",
}
LEGACY_COLUMN_NAMES = {
    "AILE": "LX", "ELEV": "LY", "THRO": "RY", "RUDD": "RX",
    "AREQ": "LXRQ", "EREQ": "LYRQ", "TREQ": "RYRQ", "RREQ": "RXRQ",
}
REQUEST_COLUMNS = ("LXRQ", "LYRQ", "RYRQ", "RXRQ")
RESPONSE_BY_REQUEST = {"LXRQ": "LX", "LYRQ": "LY", "RYRQ": "RY", "RXRQ": "RX"}
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


def _step_metrics(
    time: list[float],
    curve: list[float],
    std: list[float],
    reaction_delay_s: float | None,
) -> dict[str, float | None]:
    metrics = normalized_step_metrics(time, curve, reaction_delay_s)
    std_values = _finite(std[:min(len(time), len(curve))])
    metrics["mean_std"] = sum(std_values) / len(std_values) if std_values else None
    return metrics

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
        response_onset_s = estimate_response_onset(
            segment_time, segment, baseline_values, request_delta, sampling_hz,
        )
        metric_rows.append(_step_metrics(segment_time, segment, [], response_onset_s))
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
        original_columns = reader.fieldnames or []
        reader.fieldnames = [LEGACY_COLUMN_NAMES.get(name, name) for name in original_columns]
        columns = set(reader.fieldnames)
        if len(columns) != len(reader.fieldnames):
            raise ScopeLogError("SCoPE log contains duplicate channel names after alias normalization.")
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ScopeLogError(f"SCoPE log is missing columns: {sorted(missing)}")
        rows: list[dict[str, float]] = []
        numeric_columns = REQUIRED_COLUMNS | (OPTIONAL_COLUMNS & columns)
        for line_number, row in enumerate(reader, start=2):
            try:
                rows.append({name: float(row[name]) for name in numeric_columns if row.get(name) not in (None, "")})
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
    metrics: dict[str, float | int | None] = {
        "sample_count": len(rows), "duration_s": duration, "sampling_hz": sampling_hz,
    }
    for channel, summary in channel_summaries.items():
        for name, value in summary.items():
            metrics[f"{channel}.{name}"] = value
    normalized_response = build_normalized_step_response(rows, sampling_hz)
    for channel, response in normalized_response["channels"].items():
        for name, value in response["metrics"].items():
            metrics[f"{channel}.{name}"] = value
        metrics[f"{channel}.step_count"] = response["transition_count"]

    intervals_sorted = sorted(intervals)
    interval_mean = sum(intervals) / len(intervals)
    interval_sd = math.sqrt(sum((value - interval_mean) ** 2 for value in intervals) / len(intervals))
    action_events = _action_events(rows)
    return {
        "schema_version": "thrust-analysis-v1",
        "algorithm_version": "scope-basic-1.0.0",
        "analysis_type": "SCOPE_STEP_RESPONSE",
        "source_format": "SCoPE_TSV_V2",
        "source_file": source.name,
        "sample_count": len(rows),
        "start_time_s": times[0],
        "end_time_s": times[-1],
        "duration_s": duration,
        "estimated_sampling_hz": sampling_hz,
        "columns": sorted(columns),
        "request_transition_count": transitions,
        "channels": channel_summaries,
        "metrics": metrics,
        "quality": {
            "interval_median_s": median(intervals),
            "interval_min_s": min(intervals),
            "interval_max_s": max(intervals),
            "interval_sd_s": interval_sd,
            "relative_interval_sd": interval_sd / interval_mean if interval_mean else None,
            "intervals_over_1_5_median": sum(value > 1.5 * median(intervals) for value in intervals),
        },
        "events": action_events,
        "normalized_step_response": normalized_response,
    }


def _action_events(rows: list[dict[str, float]]) -> list[dict[str, Any]]:
    if not rows or "ACTION_ID" not in rows[0]:
        return []
    events: list[dict[str, Any]] = []
    begin = 0
    while begin < len(rows):
        action_id = rows[begin].get("ACTION_ID", 0.0)
        end = begin + 1
        while end < len(rows) and rows[end].get("ACTION_ID", 0.0) == action_id:
            end += 1
        first = rows[begin]
        segment = rows[begin:end]
        in_zone = [row.get("IN_RANGE", 0.0) for row in segment]
        events.append({
            "action_id": int(action_id),
            "start_index": begin,
            "end_index": end - 1,
            "start_time_s": first["TIME"],
            "end_time_s": segment[-1]["TIME"],
            "duration_s": segment[-1]["TIME"] - first["TIME"],
            "request": {key: first[key] for key in REQUEST_COLUMNS},
            "in_zone_fraction": sum(in_zone) / len(in_zone) if in_zone else 0.0,
            "left_in_zone_fraction": sum(row.get("LEFT_IN_ZONE", 0.0) for row in segment) / len(segment),
            "right_in_zone_fraction": sum(row.get("RIGHT_IN_ZONE", 0.0) for row in segment) / len(segment),
            "left_success": bool(max((row.get("LEFT_SUCCESS", 0.0) for row in segment), default=0.0)),
            "right_success": bool(max((row.get("RIGHT_SUCCESS", 0.0) for row in segment), default=0.0)),
            "success": bool(max((row.get("TASK_SUCCESS", 0.0) for row in segment), default=0.0)),
            "task_limit_s": first.get("TASK_LIMIT_S"),
            "hold_required_s": first.get("HOLD_REQUIRED_S"),
            "task_elapsed_s": segment[-1].get("TASK_ELAPSED_S"),
            "result_code": int(segment[-1].get("TASK_RESULT", 0.0)),
            "interrupted": int(segment[-1].get("TASK_RESULT", 0.0)) == 3,
        })
        begin = end
    return events
