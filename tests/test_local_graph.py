from thrust.analysis.local_graph import save_local_response_graph


def test_save_local_response_graph_writes_standalone_svg(tmp_path):
    raw_log = tmp_path / "SCOPE_demo.tsv.gz"
    analysis = {
        "analysis_type": "SCOPE_STEP_RESPONSE",
        "normalized_step_response": {
            "time_s": [0.0, 0.1, 0.2],
            "channels": {
                "LX": {
                    "mean": [0.0, 0.2, 0.6],
                    "median": [0.0, 0.18, 0.55],
                    "std": [0.0, 0.05, 0.1],
                    "transition_count": 3,
                }
            },
        },
    }

    graph_path = save_local_response_graph(raw_log, analysis)

    assert graph_path == tmp_path / "SCOPE_demo_response_graph.svg"
    graph = graph_path.read_text(encoding="utf-8")
    assert graph.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "LX" in graph
    assert "Mean" in graph
    assert "Median" in graph
