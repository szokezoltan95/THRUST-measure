"""Matplotlib PDF plots for normalized response curves from a measurement."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any


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


def save_local_response_graph(raw_log_path: str | Path, analysis: dict[str, Any]) -> Path:
    """Save the analysis' averaged and median responses as a local PDF."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    normalized = analysis.get("normalized_step_response")
    channels = normalized.get("channels") if isinstance(normalized, dict) else None
    if not isinstance(channels, dict) or not channels:
        raise ValueError("Analysis has no normalized response channels to plot.")

    preferred = ("LX", "LY", "RY", "RX", "x", "y")
    names = [key for key in preferred if key in channels]
    names.extend(key for key in channels if key not in names)
    is_scope = len(names) > 2
    if is_scope:
        rows, columns = 2, 2
        order = [key for key in ("LX", "LY", "RY", "RX") if key in names]
        titles = {"LX": "Left gimbal · X", "LY": "Left gimbal · Y",
                  "RY": "Right gimbal · Y", "RX": "Right gimbal · X"}
    else:
        rows, columns = len(names), 1
        order = names
        titles = {"x": "Horizontal response", "y": "Vertical response"}

    figure, axes_grid = plt.subplots(
        rows, columns, figsize=(13, 8.5 if is_scope else 8),
        squeeze=False, sharex=False, facecolor="white",
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
        if not time_s and isinstance(normalized, dict):
            time_s = _numbers(normalized.get("time_s"))
        count = max(len(mean), len(median))
        sampling_hz = normalized.get("sampling_hz", 100) if isinstance(normalized, dict) else 100
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
            axis.legend(loc="best", frameon=False, ncol=3, fontsize=9)
        axis.set_title(titles.get(key, key), loc="left", fontsize=12, fontweight="bold", pad=9)
        axis.set_ylabel("Normalized response")
        axis.grid(True, color="#d9e0e8", linewidth=0.7, alpha=0.8)
        axis.set_axisbelow(True)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#aab4c0")
        axis.spines["bottom"].set_color("#aab4c0")
        steps = channel.get("transition_count")
        if steps is not None:
            axis.text(0.99, 0.98, f"{steps} steps", transform=axis.transAxes,
                      ha="right", va="top", fontsize=8, color="#667085")

    for axis in axes:
        if axis in figure.axes:
            axis.set_xlabel("Time after input change [s]")
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
