"""Per-axis SCoPE response metrics."""
from __future__ import annotations

from itertools import zip_longest
from typing import Any

import numpy as np


def evaluate_step_response(
    data_in: Any,
    channel: str,
    creq: str,
    *,
    sampling_hz: float = 100.0,
    horizon_s: float = 2.0,
    baseline_s: float = 0.1,
) -> tuple[list[list[float]], np.ndarray, np.ndarray, np.ndarray]:
    """Build event-aligned, independently normalized responses for one axis.

    Each event is a change in that axis' own request channel. Other axes do
    not determine whether an event is accepted. Events are normalized by the
    signed request change and by the response's own pre-event baseline.

    The initial request is not treated as a response event because the log has
    no samples from before it. Its unaligned prehistory is therefore excluded.
    """
    if sampling_hz <= 0 or horizon_s <= 0 or baseline_s <= 0:
        raise ValueError("Sampling rate and response windows must be positive.")

    request = np.asarray(data_in[creq], dtype=float)
    response = np.asarray(data_in[channel], dtype=float)
    if request.ndim != 1 or response.ndim != 1 or len(request) != len(response):
        raise ValueError("Request and response channels must be equal-length series.")

    valid_pairs = np.isfinite(request[:-1]) & np.isfinite(request[1:])
    transitions = np.flatnonzero(valid_pairs & (request[1:] != request[:-1])) + 1
    if transitions.size == 0:
        raise ValueError(f"No valid steps found for {creq}")

    baseline_samples = max(3, int(round(sampling_hz * baseline_s)))
    horizon_samples = max(3, int(round(sampling_hz * horizon_s)))
    segments: list[list[float]] = []

    for event_number, index in enumerate(transitions):
        # A step at the beginning has no pre-step response baseline in the log.
        if index < baseline_samples:
            continue

        request_delta = request[index] - request[index - 1]
        if not np.isfinite(request_delta) or request_delta == 0:
            continue

        baseline_start = max(0, index - baseline_samples)
        baseline_values = response[baseline_start:index]
        baseline_values = baseline_values[np.isfinite(baseline_values)]
        if baseline_values.size < 3:
            continue
        response_baseline = float(np.median(baseline_values))

        next_transition = (
            int(transitions[event_number + 1])
            if event_number + 1 < transitions.size
            else len(response)
        )
        end = min(len(response), index + horizon_samples, next_transition)
        response_window = response[index:end]
        if response_window.size < 3:
            continue

        normalized = (response_window - response_baseline) / request_delta
        segments.append(normalized.astype(float).tolist())

    if not segments:
        raise ValueError(f"No complete response windows found for {creq}")

    aligned = np.asarray(list(zip_longest(*segments, fillvalue=np.nan)), dtype=float)
    mean = np.nanmean(aligned, axis=1)
    median = np.nanmedian(aligned, axis=1)
    std = np.nanstd(aligned, axis=1)
    return segments, median, mean, std
