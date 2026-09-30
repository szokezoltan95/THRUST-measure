from thrust.analysis.response_metrics import estimate_response_onset, normalized_step_metrics


def test_response_onset_uses_persistent_baseline_noise_threshold():
    time_s = [index / 100 for index in range(7)]
    response = [0.0, 0.005, 0.01, 0.025, 0.06, 0.10, 0.2]
    onset = estimate_response_onset(time_s, response, [0.0] * 10, 1.0, 100)

    assert onset is not None
    assert 0.02 < onset < 0.03
    assert onset < time_s[5]  # Earlier than the 10% crossing.


def test_response_onset_ignores_a_single_noise_spike():
    time_s = [index / 100 for index in range(7)]
    response = [0.0, 0.08, 0.0, 0.03, 0.04, 0.05, 0.08]
    onset = estimate_response_onset(time_s, response, [0.0] * 10, 1.0, 100)

    assert onset is not None
    assert onset > time_s[1]


def test_step_metrics_keep_rise_time_separate_from_onset():
    time_s = [index / 100 for index in range(12)]
    curve = [0.0, 0.0, 0.05, 0.12, 0.3, 0.55, 0.8, 0.95, 1.0, 1.02, 1.0, 1.0]
    metrics = normalized_step_metrics(time_s, curve, 0.015)

    assert metrics["reaction_delay_s"] == 0.015
    assert metrics["rise_time_s"] is not None
    assert metrics["rise_time_s"] > 0
    assert metrics["rise_time_s"] != metrics["reaction_delay_s"]
