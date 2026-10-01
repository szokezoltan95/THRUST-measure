from __future__ import annotations

import math
import unittest

from simple.simple_config import SimpleConfig
from simple.simple_physics import Copter, TargetSequence


class SimpleFlightTests(unittest.TestCase):
    def test_routes_stay_inside_playable_field(self) -> None:
        for pattern in ("random", "slalom", "circuit"):
            config = SimpleConfig(target_pattern=pattern)
            sequence = TargetSequence(config)
            points = [sequence.next() for _ in range(100)]
            for x, y in points:
                self.assertLessEqual(abs(x) + config.target_margin_m, config.world_width_m / 2 + 1e-9)
                self.assertGreaterEqual(y, config.target_margin_m)
                self.assertLessEqual(y + config.target_margin_m, config.world_height_m + 1e-9)
            if pattern == "circuit":
                self.assertEqual(points[0], points[config.route_points])
            if pattern == "slalom":
                self.assertNotEqual(points[0], points[config.route_points])

    def test_collision_falls_and_requires_reset(self) -> None:
        config = SimpleConfig()
        copter = Copter(config)
        self.assertEqual(copter.position[1], config.copter_radius_m)
        self.assertFalse(copter.update(0.1, 0, 0))
        for _ in range(100):
            if copter.update(0.1, 1, math.pi / 2):
                break
        self.assertTrue(copter.crashed)
        self.assertLessEqual(copter.position[0], config.world_width_m / 2 - config.copter_radius_m)
        for _ in range(100):
            copter.update(0.1, 1, 0)
        self.assertEqual(copter.position[1], config.copter_radius_m)
        self.assertTrue(copter.crashed)
        copter.reset()
        self.assertFalse(copter.crashed)
        self.assertEqual(copter.position, [0.0, config.copter_radius_m])

    def test_invalid_targets_rejected(self) -> None:
        for field in (
            {"target_x_limit_m": 2.5},
            {"target_y_min_m": 0.01},
            {"target_y_max_m": 3.0},
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                SimpleConfig(**field).validate()


if __name__ == "__main__":
    unittest.main()
