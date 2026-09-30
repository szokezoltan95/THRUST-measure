"""Matplotlib PDF plots for normalized response curves from a measurement."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any


FIXED_Y_LIMITS = (-0.2, 1.3)


def _numbers(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    result: list[float] = []
    for item in value:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            result.append(number)
    return result


def _crossing_time(time_s: list[float], values: list[float], level: float) -> float | None:
    for index, value in enumerate(values):
        if value < level:
            continue
        if index == 0:
            return time_s[0]
        previous = values[index - 1]
        delta = value - previous
        if math.isclose(delta, 0.0):
            return time_s[index]
        fraction = (level - previous) / delta
        return time_s[index - 1] + fraction * (time_s[index] - time_s[index - 1])
    return None


def _metric_text(channel: dict[str, Any], time_s: list[float],
                 mean: list[float], std: list[float]) -> str:
    metrics = channel.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}

    t10 = metrics.get("reaction_delay_s")
    if t10 is None:
        t10 = _crossing_time(time_s, mean, 0.1)
    t90 = _crossing_time(time_s, mean, 0.9)
    rise = metrics.get("rise_time_s")
    if rise is None and t10 is not None and t90 is not None:
        rise = max(0.0, t90 - t10)

    overshoot = metrics.get("overshoot_pct")
    if overshoot is None:
        overshoot = max(0.0, (max(mean) - 1.0) * 100.0) if mean else None
    max_sd = max(std) if std else None
    rmse = metrics.get("tracking_rmse")
    if rmse is None and mean:
        start = next((i for i, value in enumerate(mean) if value >= 0.1), 0)
        values = mean[start:]
        rmse = math.sqrt(sum((value - 1.0) ** 2 for value in values) / len(values)) if values else None
    settling = metrics.get("settling_time_s")

    def fmt(value: Any, suffix: str = "", digits: int = 2) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "—"
        if not math.isfinite(number):
            return "—"
        return f"{number:.{digits}f}{suffix}"

    return "\n".join((
        f"Delay (10%): {fmt(t10, ' s')}",
        f"t90: {fmt(t90, ' s')} · rise: {fmt(rise, ' s')}",
        f"Overshoot: {fmt(overshoot, '%', 1)} · max SD: {fmt(max_sd)}",
        f"RMSE: {fmt(rmse)} · settling: {fmt(settling, ' s')}",
    ))


def save_local_response_graph(raw_log_path: str | Path, analysis: dict[str, Any]) -> Path:
    """Save averaged and median response curves as a local PDF."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    normalized = analysis.get("normalized_step_response")
    channels = normalized.get("channels") if isinstance(normalized, dict) else None
    if not isinstance(channels, dict) or not channels:
        raise ValueError("Analysis has no normalized response channels to plot.")

    is_scope = any(key in channels for key in ("LX", "LY", "RY", "RX"))
    if is_scope:
        # Row-major order: both Y axes above, then both X axes.
        order = ["LY", "RY", "LX", "RX"]
        titles = {"LY": "L · Y", "RY": "R · Y", "LX": "L · X", "RX": "R · X"}
        order = [key for key in order if key in channels]
        rows, columns = 2, 2
    else:
        order = [key for key in ("x", "y") if key in channels]
        order.extend(key for key in channels if key not in order)
        titles = {"x": "X", "y": "Y"}
        rows, columns = len(order), 1

    figure, axes_grid = plt.subplots(
        rows, columns, figsize=(13, 8.5 if is_scope else 8),
        squeeze=False, facecolor="white",
    )
    axes = list(axes_grid.flat)
    horizon = normalized.get("horizon_s")
    try:
        horizon = float(horizon)
    except (TypeError, ValueError):
        horizon = 1.5 if is_scope else 5.0

    for index, axis in enumerate(axes):
        if index >= len(order):
            axis.remove()
            continue
        key = order[index]
        channel = channels[key]
        mean = _numbers(channel.get("mean"))
        median = _numbers(channel.get("median"))
        std = _numbers(channel.get("std"))
        time_s = _numbers(channel.get("time_s"))
        if not time_s:
            time_s = _numbers(normalized.get("time_s"))
        count = max(len(mean), len(median))
        sampling_hz = normalized.get("sampling_hz", 100)
        try:
            sampling_hz = float(sampling_hz)
        except (TypeError, ValueError):
            sampling_hz = 100.0
        if len(time_s) < count:
            time_s = [i / (sampling_hz if sampling_hz > 0 else 100.0) for i in range(count)]
        else:
            time_s = time_s[:count]
        mean = mean[:len(time_s)]
        median = median[:len(time_s)]
        std = std[:len(mean)]

        if not time_s or (not mean and not median):
            axis.text(0.5, 0.5, "No valid step-response data",
                      transform=axis.transAxes, ha="center", va="center", color="#667085")
        else:
            if mean:
                axis.plot(time_s[:len(mean)], mean, color="#d94c58", linewidth=2.2, label="Mean")
                if len(std) == len(mean):
                    lower = [value - deviation for value, deviation in zip(mean, std)]
                    upper = [value + deviation for value, deviation in zip(mean, std)]
                    axis.fill_between(time_s[:len(mean)], lower, upper,
                                      color="#d94c58", alpha=0.16, label="±1 SD")
            if median:
                axis.plot(time_s[:len(median)], median, color="#2878c8",
                          linewidth=2.2, label="Median")
            data_end = max(time_s) if time_s else 0.0
            axis.set_xlim(0, max(data_end, horizon if horizon > 0 else 0.1))
            axis.legend(loc="upper right", frameon=False, ncol=3, fontsize=8)
            metric_text = _metric_text(channel, time_s, mean, std)
            axis.text(
                0.98, 0.035, metric_text, transform=axis.transAxes,
                ha="right", va="bottom", fontsize=7.5, linespacing=1.35,
                family="monospace",
                bbox={"boxstyle": "round,pad=0.45", "facecolor": "white",
                      "edgecolor": "#d9e0e8", "alpha": 0.92},
            )

        axis.set_ylim(*FIXED_Y_LIMITS)
        axis.set_title(titles.get(key, key), loc="left", fontsize=12, fontweight="bold", pad=9)
        axis.set_ylabel("Normalized response")
        axis.set_xlabel("Time [s]")
        axis.grid(True, color="#d9e0e8", linewidth=0.7, alpha=0.8)
        axis.set_axisbelow(True)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#aab4c0")
        axis.spines["bottom"].set_color("#aab4c0")

    kind = "SCoPE" if is_scope else "SimPLE"
    figure.suptitle(f"{kind} · normalized step response", fontsize=17,
                    fontweight="bold", color="#202b38")
    figure.tight_layout(rect=(0, 0, 1, 0.95))

    raw_path = Path(raw_log_path)
    base = raw_path.name
    for suffix in (".gz", ".tsv", ".txt"):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
    base_dir = raw_path.parent.parent if raw_path.parent.name.lower() == "logs" else raw_path.parent
    output_dir = base_dir / "graphs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{base}_response.pdf"
    try:
        figure.savefig(output, format="pdf", bbox_inches="tight", facecolor="white")
    finally:
        plt.close(figure)
    return output
