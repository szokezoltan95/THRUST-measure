import unittest

import numpy as np
import pandas as pd

from scope.scope_metrics import evaluate_step_response


class ScopeStepResponseTests(unittest.TestCase):
    def test_does_not_wrap_final_request_into_a_fake_event_at_sample_zero(self):
        request = np.full(300, 500.0)
        request[50:] = -500.0
        response = np.full(300, 200.0)
        response[52:] = -800.0
        frame = pd.DataFrame({"LXRQ": request, "LX": response})

        segments, median, mean, std = evaluate_step_response(
            frame, "LX", "LXRQ", sampling_hz=100
        )

        self.assertEqual(len(segments), 1)
        self.assertAlmostEqual(median[0], 0.0)
        self.assertAlmostEqual(median[2], 1.0)
        self.assertAlmostEqual(mean[2], 1.0)
        self.assertAlmostEqual(std[2], 0.0)

    def test_excludes_unaligned_startup_and_uses_response_baseline_per_axis_step(self):
        request = np.full(300, -500.0)
        request[50:150] = 500.0
        response = np.full(300, 100.0)
        response[52:152] = 1100.0

        # A simultaneous change on another axis must not alter the RX samples
        # selected for RX's independent response calculation.
        other_request = np.zeros(300)
        other_request[50:] = 900.0
        frame = pd.DataFrame({
            "RXRQ": request,
            "RX": response,
            "LXRQ": other_request,
        })

        segments, median, mean, std = evaluate_step_response(
            frame, "RX", "RXRQ", sampling_hz=100
        )

        self.assertEqual(len(segments), 2)
        self.assertAlmostEqual(median[0], 0.0)
        self.assertAlmostEqual(median[2], 1.0)
        self.assertAlmostEqual(mean[0], 0.0)
        self.assertAlmostEqual(mean[2], 1.0)
        self.assertAlmostEqual(std[2], 0.0)
        self.assertTrue(np.all(np.abs(mean[:10]) <= 1.0))


if __name__ == "__main__":
    unittest.main()
