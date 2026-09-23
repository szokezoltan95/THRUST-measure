from __future__ import annotations

import csv
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    transitions = [0]
    transitions.extend(
        index for index in range(1, len(rows))
        if abs(rows[index][request] - rows[index - 1][request]) > 1e-6
    )
    pre_count = max(3, round(hz * 0.1))
    segments: list[list[float]] = []
    for order, index in enumerate(transitions):
        next_index = transitions[order + 1] if order + 1 < len(transitions) else len(rows)
        end = min(next_index, index + max(10, round(5.0 * hz)))
        if end - index < 3:
            continue
        if index == 0:
            baseline = rows[0][response]
            delta = rows[0][request]
        else:
            history = [row[response] for row in rows[max(0, index - pre_count):index]]
            baseline = statistics.median(history) if history else rows[index - 1][response]
            delta = rows[index][request] - rows[index - 1][request]
        if abs(delta) < 1e-9:
            continue
        segment = [(rows[position][response] - baseline) / delta for position in range(index, end)]
        if all(math.isfinite(value) for value in segment):
            segments.append(segment)
    return _aggregate_segments(segments, hz)


def analyze_simple_log(path: str | Path, *, started_at: str | None = None) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise SimpleLogError(f"SimPLE log does not exist: {source}")
    rows: list[dict[str, float]] = []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
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
    return {
        "schema_version": "simple-analysis-v1",
        "analysis_type": "SIMPLE_2D_FLIGHT",
        "algorithm_version": "1.0.0",
        "source_format": "SIMPLE_TSV_V1",
        "source_file": source.name,
        "started_at": started_at or datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(),
        "sample_count": len(rows),
        "duration_s": duration,
        "estimated_sampling_hz": hz,
        "metrics": metrics,
        "step_response": {
            "schema_version": "simple-normalized-response-v1",
            "channels": channels,
        },
    }


def write_step_response(path: str | Path, analysis: dict[str, Any]) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    channels = analysis["step_response"]["channels"]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("Time[s]", "XMEA", "XMED", "XSTD", "YMEA", "YMED", "YSTD"))
        x, y = channels["x"], channels["y"]
        length = max(len(x["time_s"]), len(y["time_s"]))
        for index in range(length):
            writer.writerow([
                x["time_s"][index] if index < len(x["time_s"]) else "",
                x["mean"][index] if index < len(x["mean"]) else "",
                x["median"][index] if index < len(x["median"]) else "",
                x["std"][index] if index < len(x["std"]) else "",
                y["mean"][index] if index < len(y["mean"]) else "",
                y["median"][index] if index < len(y["median"]) else "",
                y["std"][index] if index < len(y["std"]) else "",
            ])
    return str(target)


def save_step_graph(path: str | Path, analysis: dict[str, Any]) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    channels = analysis["step_response"]["channels"]
    figure, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    for axis, key, title in zip(axes, ("x", "y"), ("Horizontal response", "Vertical response")):
        channel = channels[key]
        axis.plot(channel["time_s"], channel["mean"], color="#ef5c63", label="Mean")
        axis.plot(channel["time_s"], channel["median"], color="#48b9e8", label="Median")
        lower = [mean - std for mean, std in zip(channel["mean"], channel["std"])]
        upper = [mean + std for mean, std in zip(channel["mean"], channel["std"])]
        axis.fill_between(channel["time_s"], lower, upper, color="#ef5c63", alpha=0.18, label="±1 SD")
        axis.set_xlim(0, 5)
        axis.set_ylabel("Normalized response")
        axis.set_title(title)
        axis.grid(True, alpha=0.25)
        axis.legend(loc="best")
    axes[-1].set_xlabel("Time after target change [s]")
    figure.tight_layout()
    figure.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(target)
