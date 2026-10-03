import csv
import tempfile
import unittest
from pathlib import Path

from thrust.analysis.scope_log import analyze_scope_log


class ScopeAnalysisTests(unittest.TestCase):
    def test_records_total_and_per_gimbal_task_results_and_interruptions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope.tsv"
            columns = ["TIME", "LX", "LY", "RY", "RX", "LXRQ", "LYRQ", "RYRQ", "RXRQ",
                       "IRRS", "ACTION_ID", "IN_RANGE", "LEFT_IN_ZONE", "RIGHT_IN_ZONE",
                       "LEFT_SUCCESS", "RIGHT_SUCCESS", "TASK_SUCCESS", "TASK_LIMIT_S",
                       "HOLD_REQUIRED_S", "TASK_ELAPSED_S", "TASK_RESULT"]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, delimiter="\t")
                writer.writerow(columns)
                for index, (task, result, overall, left_ok, right_ok) in enumerate([
                    (1, 0, 0, 0, 0), (1, 1, 1, 1, 1),
                    (2, 0, 0, 1, 0), (2, 3, 0, 1, 0),
                ]):
                    writer.writerow([index * .1, 0, 0, 0, 0, 10, 0, 0, 0, 0, task,
                                     overall, left_ok, right_ok, left_ok, right_ok, overall,
                                     4, 1, index * .1, result])
            result = analyze_scope_log(path)

        self.assertEqual([event["result_code"] for event in result["events"]], [1, 3])
        self.assertTrue(result["events"][0]["success"])
        self.assertTrue(result["events"][0]["left_success"])
        self.assertTrue(result["events"][0]["right_success"])
        self.assertTrue(result["events"][1]["interrupted"])
        self.assertEqual(result["events"][0]["task_limit_s"], 4)
        self.assertEqual(result["events"][0]["hold_required_s"], 1)

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
