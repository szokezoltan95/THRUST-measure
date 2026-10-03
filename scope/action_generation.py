"""Generate discrete SCoPE target transitions from versioned test settings."""
from __future__ import annotations

import random
import math
from typing import Any

AXES = ("LX", "LY", "RY", "RX")
GIMBALS = ((0, 1), (2, 3))
TIMING_SCHEDULE_VERSION = 1
DEFAULT_ACTION_SETTINGS: dict[str, Any] = {
    "generator_version": 1,
    "intervals": {axis: [-0.8, 0.8] for axis in AXES},
    "points_per_axis": 9,
    "min_changed_axes": 1,
    "max_changed_axes": 2,
    "single_gimbal_probability": 0.5,
}


def balanced_timing_schedule(count: int, low_s: float, high_s: float, rng: random.Random) -> list[float]:
    """Return a shuffled, stratified schedule spanning the configured range.

    Stratification keeps the mean close to the range midpoint and distributes
    durations evenly; shuffling prevents a predictable short-to-long sequence.
    The complete schedule has an exact midpoint mean; a one-task schedule uses
    that midpoint. Equal bounds remain deterministic.
    """
    if count <= 0 or not math.isfinite(low_s) or not math.isfinite(high_s) or low_s <= 0 or low_s > high_s:
        raise ValueError("Timing schedule requires count > 0 and 0 < min <= max")
    if low_s == high_s:
        return [float(low_s)] * count
    values = [low_s + (high_s - low_s) * ((index + 0.5) / count) for index in range(count)]
    rng.shuffle(values)
    return values


def _quantize(normalized_value: float, stick_max: int) -> int:
    # Match JavaScript Math.round so the browser and measure validate/build the
    # same discrete levels, including half-value boundaries.
    return math.floor(normalized_value * stick_max + 0.5)


def validate_action_settings(settings: dict[str, Any], stick_max: int | None = None) -> None:
    intervals = settings.get("intervals")
    if not isinstance(intervals, dict):
        raise ValueError("action_settings.intervals must be an object")
    for axis in AXES:
        bounds = intervals.get(axis)
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise ValueError(f"action_settings interval for {axis} must have [min, max]")
        low, high = bounds
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
            raise ValueError(f"action_settings interval for {axis} must be numeric")
        if not -1 <= low < high <= 1:
            raise ValueError(f"action_settings interval for {axis} must satisfy -1 <= min < max <= 1")
    points = settings.get("points_per_axis")
    if not isinstance(points, int) or isinstance(points, bool) or not 2 <= points <= 101:
        raise ValueError("action_settings.points_per_axis must be an integer from 2 to 101")
    minimum = settings.get("min_changed_axes")
    maximum = settings.get("max_changed_axes")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or not 1 <= minimum <= 4:
        raise ValueError("action_settings.min_changed_axes must be from 1 to 4")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or not minimum <= maximum <= 4:
        raise ValueError("action_settings.max_changed_axes must be between min_changed_axes and 4")
    probability = settings.get("single_gimbal_probability")
    if not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
        raise ValueError("action_settings.single_gimbal_probability must be between 0 and 1")
    if stick_max is not None:
        for axis in AXES:
            low, high = intervals[axis]
            quantized = {
                _quantize(low + (high - low) * index / (points - 1), stick_max)
                for index in range(points)
            }
            if len(quantized) != points:
                raise ValueError(
                    f"Interval for {axis} and points_per_axis produce duplicate joystick values; "
                    "widen the interval, reduce the point count or increase stick_max"
                )


def _axis_values(settings: dict[str, Any], stick_max: int) -> list[list[int]]:
    point_count = settings["points_per_axis"]
    values: list[list[int]] = []
    for axis in AXES:
        low, high = settings["intervals"][axis]
        levels = [low + (high - low) * index / (point_count - 1) for index in range(point_count)]
        values.append(list(dict.fromkeys(_quantize(value, stick_max) for value in levels)))
    for axis, axis_levels in zip(AXES, values):
        if len(axis_levels) != point_count:
            raise ValueError(f"Interval for {axis} produces duplicate joystick values")
    return values


def generate_next_target(
    previous: list[int], settings: dict[str, Any], stick_max: int, rng: random.Random,
) -> list[int]:
    """Choose grid values, changing 1..max axes relative to the prior target.

    With the configured probability, only one gimbal's target coordinates may
    change. This constrains the target transition; it does not command the
    participant's physical stick position.
    """
    validate_action_settings(settings)
    levels = _axis_values(settings, stick_max)
    min_count = settings["min_changed_axes"]
    max_count = settings["max_changed_axes"]
    changed_count = rng.randint(min_count, max_count)

    single_gimbal = (
        changed_count <= 2
        and rng.random() < settings["single_gimbal_probability"]
    )
    if single_gimbal:
        eligible = [group for group in GIMBALS if len(group) >= changed_count]
        candidate_axes = list(rng.choice(eligible))
    else:
        candidate_axes = list(range(len(AXES)))
    changed_axes = rng.sample(candidate_axes, changed_count)

    target = list(previous)
    for index in changed_axes:
        choices = [value for value in levels[index] if value != previous[index]]
        if not choices:
            # This can occur only when a custom interval collapses to one
            # integer after scaling. Configuration validation normally keeps
            # a useful grid; report it explicitly if scale is too small.
            raise ValueError(f"Axis {AXES[index]} has no alternative target value")
        target[index] = rng.choice(choices)
    return target
