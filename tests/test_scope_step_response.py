import csv
import tempfile
import unittest
from pathlib import Path

from thrust.analysis.scope_log import analyze_scope_log


class ScopeAnalysisTests(unittest.TestCase):
    def test_analyzes_raw_scope_tsv_without_optional_numeric_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope.tsv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, delimiter="\t")
                writer.writerow(["TIME", "LX", "LY", "RY", "RX", "LXRQ", "LYRQ", "RYRQ", "RXRQ", "ACTION_ID", "IN_RANGE"])
                for index in range(200):
                    request = -500 if index < 50 else 500
                    response = -400 if index < 53 else 400
                    writer.writerow([index / 100, response, 0, 0, 0, request, 0, 0, 0, 1, int(index > 55)])
            result = analyze_scope_log(path)

        self.assertEqual(result["schema_version"], "thrust-analysis-v1")
        self.assertEqual(result["sample_count"], 200)
        self.assertEqual(result["normalized_step_response"]["channels"]["LX"]["transition_count"], 1)
        self.assertEqual(result["events"][0]["action_id"], 1)
        self.assertIn("LX.rise_time_s", result["metrics"])


if __name__ == "__main__":
    unittest.main()
