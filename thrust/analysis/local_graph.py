"""Lightweight local SVG plots for the normalized response curves.

The plots are generated from the same response summaries stored in the analysis
artifact. SVG is written directly so local graph creation adds no dependency.
"""
from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any


COLORS = {
    "mean": "#38a6ff",
    "median": "#ff9b54",
    "band": "#38a6ff",
    "grid": "#d6dce5",
    "axis": "#6f7c8d",
    "text": "#263342",
}


def _numbers(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    output: list[float] = []
    for item in value:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            output.append(number)
    return output


def _points(xs: list[float], ys: list[float], x: Any, y: Any, width: Any, height: Any,
            xmin: float, xmax: float, ymin: float, ymax: float) -> list[tuple[float, float]]:
    count = min(len(xs), len(ys))
    xspan = xmax - xmin or 1.0
    yspan = ymax - ymin or 1.0
    return [
        (x + (xs[i] - xmin) / xspan * width, y + height - (ys[i] - ymin) / yspan * height)
        for i in range(count)
    ]


def _polyline(points: list[tuple[float, float]], color: str, width: int = 3) -> str:
    if not points:
        return ""
    coords = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
    return f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


def _panel(channel_name: str, channel: dict[str, Any], fallback_time: list[float],
           x: float, y: float, width: float, height: float) -> str:
    mean = _numbers(channel.get("mean"))
    median = _numbers(channel.get("median"))
    std = _numbers(channel.get("std"))
    time_values = _numbers(channel.get("time_s")) or fallback_time
    count = max(len(mean), len(median))
    xs = time_values[:count] if len(time_values) >= count else [i / 100.0 for i in range(count)]
    if len(xs) < count:
        xs += [((xs[-1] if xs else 0.0) + (i + 1) / 100.0) for i in range(count - len(xs))]
    if count == 0:
        return (
            f'<g><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="12" fill="#ffffff" stroke="#d6dce5"/>'
            f'<text x="{x + 20}" y="{y + 30}" font-size="19" font-weight="700" fill="{COLORS["text"]}">{html.escape(channel_name)}</text>'
            f'<text x="{x + 20}" y="{y + 80}" font-size="15" fill="{COLORS["axis"]}">No valid step-response data</text></g>'
        )

    all_values = mean + median
    for index, value in enumerate(mean[:len(std)]):
        all_values.extend((value - std[index], value + std[index]))
    ymin, ymax = min(all_values), max(all_values)
    if math.isclose(ymin, ymax):
        ymin -= 0.1
        ymax += 0.1
    padding = (ymax - ymin) * 0.08
    ymin -= padding
    ymax += padding
    xmax = max(xs) if xs else 0.0
    if xmax <= 0:
        xmax = 1.0

    left, top, right, bottom = 58, 54, 18, 48
    plot_x, plot_y = x + left, y + top
    plot_w, plot_h = width - left - right, height - top - bottom
    parts = [
        f'<g><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="12" fill="#ffffff" stroke="#d6dce5"/>',
        f'<text x="{x + 18}" y="{y + 29}" font-size="19" font-weight="700" fill="{COLORS["text"]}">{html.escape(channel_name)}</text>',
        f'<text x="{x + width - 18}" y="{y + 28}" text-anchor="end" font-size="12" fill="{COLORS["axis"]}">{int(channel.get("transition_count") or 0)} steps</text>',
    ]
    for tick in range(5):
        gy = plot_y + plot_h * tick / 4
        label = ymax - (ymax - ymin) * tick / 4
        parts.append(f'<line x1="{plot_x}" y1="{gy:.1f}" x2="{plot_x + plot_w}" y2="{gy:.1f}" stroke="{COLORS["grid"]}"/>')
        parts.append(f'<text x="{plot_x - 8}" y="{gy + 4:.1f}" text-anchor="end" font-size="10" fill="{COLORS["axis"]}">{label:.2f}</text>')
    parts.extend((
        f'<line x1="{plot_x}" y1="{plot_y}" x2="{plot_x}" y2="{plot_y + plot_h}" stroke="{COLORS["axis"]}"/>',
        f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y + plot_h}" stroke="{COLORS["axis"]}"/>',
    ))
    for tick in range(5):
        gx = plot_x + plot_w * tick / 4
        label = xmax * tick / 4
        parts.append(f'<line x1="{gx:.1f}" y1="{plot_y + plot_h}" x2="{gx:.1f}" y2="{plot_y + plot_h + 4}" stroke="{COLORS["axis"]}"/>')
        parts.append(f'<text x="{gx:.1f}" y="{plot_y + plot_h + 19}" text-anchor="middle" font-size="10" fill="{COLORS["axis"]}">{label:.2f}</text>')

    mean_pts = _points(xs, mean, plot_x, plot_y, plot_w, plot_h, 0, xmax, ymin, ymax)
    median_pts = _points(xs, median, plot_x, plot_y, plot_w, plot_h, 0, xmax, ymin, ymax)
    n = min(len(mean), len(std), len(xs))
    if n > 1:
        upper = _points(xs[:n], [mean[i] + std[i] for i in range(n)], plot_x, plot_y, plot_w, plot_h, 0, xmax, ymin, ymax)
        lower = _points(xs[:n], [mean[i] - std[i] for i in range(n)], plot_x, plot_y, plot_w, plot_h, 0, xmax, ymin, ymax)
        polygon = " ".join(f"{px:.1f},{py:.1f}" for px, py in upper + list(reversed(lower)))
        parts.append(f'<polygon points="{polygon}" fill="{COLORS["band"]}" opacity="0.13"/>')
    parts.extend((_polyline(mean_pts, COLORS["mean"]), _polyline(median_pts, COLORS["median"])))
    legend_y = y + height - 12
    parts.extend((
        f'<line x1="{x + 22}" y1="{legend_y - 4}" x2="{x + 42}" y2="{legend_y - 4}" stroke="{COLORS["mean"]}" stroke-width="3"/>',
        f'<text x="{x + 47}" y="{legend_y}" font-size="11" fill="{COLORS["text"]}">Mean</text>',
        f'<line x1="{x + 110}" y1="{legend_y - 4}" x2="{x + 130}" y2="{legend_y - 4}" stroke="{COLORS["median"]}" stroke-width="3"/>',
        f'<text x="{x + 135}" y="{legend_y}" font-size="11" fill="{COLORS["text"]}">Median</text>',
        f'<text x="{x + width - 18}" y="{legend_y}" text-anchor="end" font-size="10" fill="{COLORS["axis"]}">time [s] · normalized response</text>',
        '</g>',
    ))
    return "".join(parts)


def save_local_response_graph(raw_log_path: str | Path, analysis: dict[str, Any]) -> Path:
    """Save mean/median normalized response plots beside the raw log as SVG."""
    normalized = analysis.get("normalized_step_response")
    channels = normalized.get("channels") if isinstance(normalized, dict) else None
    if not isinstance(channels, dict) or not channels:
        raise ValueError("Analysis has no normalized response channels to plot.")

    channel_names = [name for name in ("LX", "LY", "RY", "RX", "x", "y") if name in channels]
    channel_names.extend(name for name in channels if name not in channel_names)
    time_values = _numbers(normalized.get("time_s"))
    columns = 2
    panel_w, panel_h, gap = 600, 360, 24
    rows = math.ceil(len(channel_names) / columns)
    margin = 24
    width = margin * 2 + columns * panel_w + gap
    height = margin * 2 + rows * panel_h + gap * max(0, rows - 1) + 64
    title = "SCoPE normalized step response" if len(channel_names) > 2 else "SimPLE normalized step response"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f2f5f9"/>',
        f'<text x="{margin}" y="38" font-family="Segoe UI, Arial, sans-serif" font-size="24" font-weight="700" fill="{COLORS["text"]}">{title}</text>',
    ]
    for index, name in enumerate(channel_names):
        row, column = divmod(index, columns)
        px = margin + column * (panel_w + gap)
        py = margin + 44 + row * (panel_h + gap)
        parts.append(_panel(name, channels[name], time_values, px, py, panel_w, panel_h))
    parts.append("</svg>")

    raw_path = Path(raw_log_path)
    base = raw_path.name
    if base.endswith(".gz"):
        base = base[:-3]
    if base.endswith(".tsv"):
        base = base[:-4]
    if base.endswith(".txt"):
        base = base[:-4]
    output = raw_path.with_name(f"{base}_response_graph.svg")
    output.write_text("\n".join(parts), encoding="utf-8")
    return output
