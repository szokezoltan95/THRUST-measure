import matplotlib.pyplot as plt

from thrust.analysis.local_graph import FIXED_Y_LIMITS, save_local_response_graph


def test_save_local_response_graph_writes_comparable_scope_pdf(tmp_path, monkeypatch):
    raw_log = tmp_path / "SCOPE_demo.tsv.gz"
    names = ("LX", "LY", "RY", "RX")
    analysis = {
        "normalized_step_response": {
            "horizon_s": 1.5,
            "sampling_hz": 100,
            "time_s": [0.0, 0.1, 0.2],
            "channels": {
                name: {
                    "mean": [0.0, 0.2, 0.6],
                    "median": [0.0, 0.18, 0.55],
                    "std": [0.0, 0.05, 0.1],
                    "transition_count": 3,
                    "metrics": {
                        "reaction_delay_s": 0.05,
                        "rise_time_s": 0.17,
                        "overshoot_pct": 8.0,
                        "settling_time_s": 0.3,
                        "tracking_rmse": 0.21,
                    },
                }
                for name in names
            },
        },
    }

    original_subplots = plt.subplots
    captured = []

    def capture_subplots(*args, **kwargs):
        figure, axes = original_subplots(*args, **kwargs)
        captured.append((figure, axes))
        return figure, axes

    monkeypatch.setattr(plt, "subplots", capture_subplots)
    analysis["started_at"] = "2026-09-30T12:34:56+00:00"
    graph_path = save_local_response_graph(raw_log, analysis, participant_id="THRUST-001")

    assert graph_path == tmp_path / "graphs" / "SCOPE_demo_response.pdf"
    assert graph_path.read_bytes().startswith(b"%PDF-")
    figure = captured[0][0]
    axes = captured[0][1].flat
    assert [axis.get_title(loc="left") for axis in axes] == ["L · Y", "R · Y", "L · X", "R · X"]
    assert all(tuple(axis.get_ylim()) == FIXED_Y_LIMITS for axis in axes)
    assert all(axis.get_xlabel() == "Time [s]" for axis in axes)
    assert all("Max SD" in axis.texts[-1].get_text() for axis in axes)
    assert "Participant ID: THRUST-001" in figure.texts[1].get_text()
    assert "Test date/time: 2026-09-30" in figure.texts[1].get_text()
    assert all(axis.get_legend()._loc == 4 for axis in axes)
