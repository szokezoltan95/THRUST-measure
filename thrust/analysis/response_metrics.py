"""Noise-aware onset and standard step-response metrics."""
from __future__ import annotations

import math
from statistics import median
from typing import Any


def estimate_response_onset(
    time_s: list[float],
    normalized_response: list[float],
    baseline_values: list[float],
    input_step: float,
    sampling_hz: float,
) -> float | None:
    """Estimate detectable response onset using baseline MAD and persistence.

    The normalized threshold is max(2% of the input step, 3 robust baseline
    standard deviations). A crossing must persist for about 30 ms.
    """
    count = min(len(time_s), len(normalized_response))
    if count < 3 or len(baseline_values) < 3 or not math.isfinite(input_step) or input_step == 0:
        return None
    baseline = [float(value) for value in baseline_values if math.isfinite(float(value))]
    if len(baseline) < 3:
        return None
    baseline_center = median(baseline)
    mad = median([abs(value - baseline_center) for value in baseline])
    noise_sigma_normalized = 1.4826 * mad / abs(input_step)
    threshold = max(0.02, 3.0 * noise_sigma_normalized)
    persistence = max(2, round(max(1.0, sampling_hz) * 0.03))
    response = [float(value) for value in normalized_response[:count]]
    times = [float(value) for value in time_s[:count]]

    for start in range(0, count - persistence + 1):
        if not all(math.isfinite(value) and abs(value) >= threshold
                   for value in response[start:start + persistence]):
            continue
        current = abs(response[start])
        if start == 0:
            return max(0.0, times[start])
        previous = abs(response[start - 1])
        delta = current - previous
        if delta <= 0:
            return max(0.0, times[start])
        fraction = min(1.0, max(0.0, (threshold - previous) / delta))
        return max(0.0, times[start - 1] + fraction * (times[start] - times[start - 1]))
    return None


def _crossing_time(time_s: list[float], curve: list[float], level: float) -> float | None:
    for index, value in enumerate(curve):
        if value < level:
            continue
        if index == 0:
            return time_s[0]
        previous = curve[index - 1]
        delta = value - previous
        if math.isclose(delta, 0.0):
            return time_s[index]
        fraction = (level - previous) / delta
        return time_s[index - 1] + fraction * (time_s[index] - time_s[index - 1])
    return None


def normalized_step_metrics(
    time_s: list[float],
    curve: list[float],
    reaction_delay_s: float | None,
) -> dict[str, float | None]:
    """Compute standard metrics for one normalized unit-step response."""
    count = min(len(time_s), len(curve))
    empty = {
        "reaction_delay_s": reaction_delay_s,
        "rise_time_s": None,
        "overshoot_pct": None,
        "settling_time_s": None,
        "steady_state_error_pct": None,
        "tracking_rmse": None,
    }
    if count < 3:
        return empty
    times = time_s[:count]
    values = curve[:count]
    t10 = _crossing_time(times, values, 0.1)
    t90 = _crossing_time(times, values, 0.9)
    last_outside = -1
    for index, value in enumerate(values):
        if abs(value - 1.0) > 0.05:
            last_outside = index
    settling = times[last_outside] if 0 <= last_outside < count - 1 else None
    final_count = max(1, count // 10)
    final_value = sum(values[-final_count:]) / final_count
    rmse_start = next((index for index, value in enumerate(values) if value >= 0.1), 0)
    rmse_values = values[rmse_start:]
    rmse = math.sqrt(sum((value - 1.0) ** 2 for value in rmse_values) / len(rmse_values))
    return {
        "reaction_delay_s": reaction_delay_s,
        "rise_time_s": max(0.0, t90 - t10) if t10 is not None and t90 is not None else None,
        "overshoot_pct": max(0.0, (max(values) - 1.0) * 100.0),
        "settling_time_s": settling,
        "steady_state_error_pct": abs(1.0 - final_value) * 100.0,
        "tracking_rmse": rmse,
    }
