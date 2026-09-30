from __future__ import annotations

import csv
import gzip
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thrust.analysis.response_metrics import estimate_response_onset, normalized_step_metrics

REQUIRED_COLUMNS = {"Time[s]", "POSX", "POSY", "REQX", "REQY"}


class SimpleLogError(ValueError):
    pass


def _aggregate_segments(segments: list[list[float]], hz: float) -> dict[str, Any]:
    count = max((len(segment) for segment in segments), default=0)
    mean_curve: list[float] = []
    median_curve: list[float] = []
    std_curve: list[float] = []
    for index in range(count):
        values = [segment[index] for segment in segments if index < len(segment)]
        if not values:
            continue
        average = statistics.fmean(values)
        mean_curve.append(average)
        median_curve.append(statistics.median(values))
        std_curve.append(math.sqrt(statistics.fmean((value - average) ** 2 for value in values)))
    return {
        "mean": mean_curve,
        "median": median_curve,
        "std": std_curve,
        "time_s": [index / hz for index in range(len(mean_curve))],
        "transition_count": len(segments),
    }


def _step_response(rows: list[dict[str, float]], request: str, response: str, hz: float) -> dict[str, Any]:
    transitions = [
        index for index in range(1, len(rows))
        if abs(rows[index][request] - rows[index - 1][request]) > 1e-6
    ]
    pre_count = max(3, round(hz * 0.1))
    segments: list[list[float]] = []
    metric_rows: list[dict[str, float | None]] = []
    for order, index in enumerate(transitions):
        next_index = transitions[order + 1] if order + 1 < len(transitions) else len(rows)
        end = min(next_index, index + max(10, round(5.0 * hz)))
        if end - index < 3:
            continue
        history = [row[response] for row in rows[max(0, index - pre_count):index]]
        baseline = statistics.median(history) if history else rows[index - 1][response]
        delta = rows[index][request] - rows[index - 1][request]
        if abs(delta) < 1e-9:
            continue
        segment = [(rows[position][response] - baseline) / delta for position in range(index, end)]
        if not all(math.isfinite(value) for value in segment):
            continue
        segment_time = [rows[position]["Time[s]"] - rows[index]["Time[s]"] for position in range(index, end)]
        segments.append(segment)
        onset = estimate_response_onset(segment_time, segment, history, delta, hz)
        metric_rows.append(normalized_step_metrics(segment_time, segment, onset))

    result = _aggregate_segments(segments, hz)
    metric_names = (
        "reaction_delay_s", "rise_time_s", "overshoot_pct", "settling_time_s",
        "steady_state_error_pct", "tracking_rmse",
    )
    metrics: dict[str, Any] = {"aggregation": "median", "step_count": len(metric_rows)}
    for name in metric_names:
        values = [float(item[name]) for item in metric_rows if item.get(name) is not None]
        metrics[name] = statistics.median(values) if values else None
        metrics[f"{name}_mean"] = statistics.fmean(values) if values else None
    metrics["mean_std"] = statistics.fmean(result["std"]) if result["std"] else None
    metrics["mean_std_mean"] = metrics["mean_std"]
    result["metrics"] = metrics
    return result
def analyze_simple_log(path: str | Path, *, started_at: str | None = None) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise SimpleLogError(f"SimPLE log does not exist: {source}")
    rows: list[dict[str, float]] = []
    opener = gzip.open if source.suffix == ".gz" else open
    with opener(source, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise SimpleLogError(f"SimPLE log is missing columns: {sorted(missing)}")
        numeric_columns = REQUIRED_COLUMNS | (
            {"IN_ZONE", "ACTION", "RESET", "ROLL", "THROTTLE"}
            & set(reader.fieldnames or [])
        )
        for line, raw in enumerate(reader, start=2):
            try:
                row = {
                    name: float(raw[name])
                    for name in numeric_columns
                    if raw.get(name) not in (None, "")
                }
            except (TypeError, ValueError, KeyError) as exc:
                raise SimpleLogError(f"Invalid numeric value on line {line}.") from exc
            if not REQUIRED_COLUMNS.issubset(row):
                raise SimpleLogError(f"Required values are missing on line {line}.")
            if not all(math.isfinite(value) for value in row.values()):
                raise SimpleLogError(f"Non-finite value on line {line}.")
            rows.append(row)
    if len(rows) < 2:
        raise SimpleLogError("SimPLE log must contain at least two samples.")
    times = [row["Time[s]"] for row in rows]
    intervals = [right - left for left, right in zip(times, times[1:])]
    if any(interval <= 0 for interval in intervals):
        raise SimpleLogError("SimPLE Time[s] values must be strictly increasing.")
    hz = 1 / statistics.median(intervals)
    duration = times[-1] - times[0]
    interval_mean = statistics.fmean(intervals)
    interval_sd = math.sqrt(statistics.fmean((value - interval_mean) ** 2 for value in intervals))
    x_error = [row["REQX"] - row["POSX"] for row in rows]
    y_error = [row["REQY"] - row["POSY"] for row in rows]
    distances = [math.hypot(x, y) for x, y in zip(x_error, y_error)]
    in_zone = [float(row.get("IN_ZONE", 0.0)) for row in rows]
    actions = [row.get("ACTION", 0.0) for row in rows]
    resets = [row.get("RESET", 0.0) for row in rows]
    action_count = max(actions, default=0.0)
    reset_edges = sum(1 for index, value in enumerate(resets) if value > 0.5 and (index == 0 or resets[index - 1] <= 0.5))
    channels = {
        "x": _step_response(rows, "REQX", "POSX", hz),
        "y": _step_response(rows, "REQY", "POSY", hz),
    }
    metrics = {
        "sample_count": len(rows),
        "duration_s": duration,
        "sampling_hz": hz,
        "simple_duration_s": duration,
        "simple_sample_count": len(rows),
        "simple_sampling_hz": hz,
        "simple_action_count": action_count,
        "simple_reset_count": reset_edges,
        "simple_mean_target_error_m": statistics.fmean(distances),
        "simple_median_target_error_m": statistics.median(distances),
        "simple_rms_target_error_m": math.sqrt(statistics.fmean(value * value for value in distances)),
        "simple_in_zone_fraction": statistics.fmean(in_zone),
        "simple_x_step_count": channels["x"]["transition_count"],
        "simple_y_step_count": channels["y"]["transition_count"],
    }
    events = []
    if "ACTION" in rows[0]:
        begin = 0
        while begin < len(rows):
            action_id = rows[begin].get("ACTION", 0.0)
            end = begin + 1
            while end < len(rows) and rows[end].get("ACTION", 0.0) == action_id:
                end += 1
            first, segment = rows[begin], rows[begin:end]
            events.append({
                "action_id": int(action_id), "start_index": begin, "end_index": end - 1,
                "start_time_s": first["Time[s]"], "end_time_s": segment[-1]["Time[s]"],
                "duration_s": segment[-1]["Time[s]"] - first["Time[s]"],
                "request": {"x": first["REQX"], "y": first["REQY"]},
                "in_zone_fraction": statistics.fmean(row.get("IN_ZONE", 0.0) for row in segment),
                "reset_count": sum(
                    1 for index, row in enumerate(segment)
                    if row.get("RESET", 0.0) > 0.5
                    and (index == 0 or segment[index - 1].get("RESET", 0.0) <= 0.5)
                ),
            })
            begin = end
    return {
        "schema_version": "thrust-analysis-v1",
        "analysis_type": "SIMPLE_2D_FLIGHT",
        "algorithm_version": "simple-basic-1.0.0",
        "source_format": "SIMPLE_TSV_V1",
        "source_file": source.name,
        "started_at": started_at or datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(),
        "sample_count": len(rows),
        "duration_s": duration,
        "estimated_sampling_hz": hz,
        "metrics": metrics,
        "quality": {
            "interval_median_s": statistics.median(intervals),
            "interval_min_s": min(intervals),
            "interval_max_s": max(intervals),
            "interval_sd_s": interval_sd,
            "relative_interval_sd": interval_sd / interval_mean if interval_mean else None,
            "intervals_over_1_5_median": sum(value > 1.5 * statistics.median(intervals) for value in intervals),
        },
        "events": events,
        "normalized_step_response": {
            "schema_version": "simple-normalized-response-v1",
            "channels": channels,
        },
    }
