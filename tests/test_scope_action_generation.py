import random
import unittest

from scope.action_generation import DEFAULT_ACTION_SETTINGS, balanced_timing_schedule, generate_next_target
from scope.scope_config import ScopeConfig


class ScopeActionGenerationTests(unittest.TestCase):
    def test_balanced_timing_schedule_has_exact_midpoint_average_and_seeded_order(self):
        first = balanced_timing_schedule(20, 3, 5, random.Random(17))
        second = balanced_timing_schedule(20, 3, 5, random.Random(17))
        self.assertEqual(first, second)
        self.assertEqual(sum(first) / len(first), 4.0)
        self.assertGreater(len(set(first)), 1)
        self.assertTrue(all(3 <= value <= 5 for value in first))

    def test_one_task_uses_range_midpoint(self):
        self.assertEqual(balanced_timing_schedule(1, 3, 5, random.Random(2)), [4.0])

    def test_limits_changed_axes_relative_to_previous_target(self):
        settings = {
            **DEFAULT_ACTION_SETTINGS,
            "intervals": {axis: [-0.8, 0.8] for axis in ("LX", "LY", "RY", "RX")},
            "points_per_axis": 9,
            "min_changed_axes": 1,
            "max_changed_axes": 2,
            "single_gimbal_probability": 0,
        }
        previous = [0, 0, 0, 0]
        rng = random.Random(41)
        for _ in range(100):
            target = generate_next_target(previous, settings, 1000, rng)
            changed = sum(a != b for a, b in zip(previous, target))
            self.assertGreaterEqual(changed, 1)
            self.assertLessEqual(changed, 2)
            previous = target

    def test_single_gimbal_policy_preserves_the_other_gimbal_targets(self):
        settings = {
            **DEFAULT_ACTION_SETTINGS,
            "intervals": {axis: [-0.8, 0.8] for axis in ("LX", "LY", "RY", "RX")},
            "points_per_axis": 9,
            "min_changed_axes": 1,
            "max_changed_axes": 2,
            "single_gimbal_probability": 1,
        }
        previous = [200, -400, 600, -200]
        target = generate_next_target(previous, settings, 1000, random.Random(7))
        left_changed = target[:2] != previous[:2]
        right_changed = target[2:] != previous[2:]
        self.assertNotEqual(left_changed, right_changed)

    def test_zero_is_a_regular_grid_value_and_can_be_a_transition_target(self):
        settings = {
            **DEFAULT_ACTION_SETTINGS,
            "intervals": {axis: [-1, 1] for axis in ("LX", "LY", "RY", "RX")},
            "points_per_axis": 3,
            "min_changed_axes": 1,
            "max_changed_axes": 1,
            "single_gimbal_probability": 0,
        }
        previous = [1000, 1000, 1000, 1000]
        rng = random.Random(19)
        observed_zero = False
        for _ in range(50):
            target = generate_next_target(previous, settings, 1000, rng)
            observed_zero |= any(old != 0 and new == 0 for old, new in zip(previous, target))
            previous = target
        self.assertTrue(observed_zero)

    def test_seed_reproduces_the_same_target_sequence(self):
        settings = {
            **DEFAULT_ACTION_SETTINGS,
            "intervals": {axis: [-0.8, 0.8] for axis in ("LX", "LY", "RY", "RX")},
        }

        def sequence(seed):
            rng = random.Random(seed)
            point = [0, 0, 0, 0]
            result = []
            for _ in range(12):
                point = generate_next_target(point, settings, 1000, rng)
                result.append(point)
            return result

        self.assertEqual(sequence(1234), sequence(1234))

    def test_scope_config_round_trips_action_settings_without_old_difficulty(self):
        config = ScopeConfig()
        config.validate()
        payload = config.to_dict()
        self.assertNotIn("difficulty", payload)
        restored = ScopeConfig.from_dict(payload)
        restored.validate()
        self.assertEqual(restored.action_settings, config.action_settings)

    def test_config_rejects_grid_points_that_collapse_to_duplicate_joystick_values(self):
        config = ScopeConfig(stick_max=200)
        config.action_settings["intervals"]["LX"] = [-0.005, 0.005]
        with self.assertRaisesRegex(ValueError, "duplicate joystick values"):
            config.validate()

    def test_version_two_fixed_duration_range_is_limited_to_three_to_five_seconds(self):
        config = ScopeConfig(timing_version=2, timing_mode="fixed_duration", task_duration_min_s=2.9)
        with self.assertRaisesRegex(ValueError, "3 to 5 seconds"):
            config.validate()


if __name__ == "__main__":
    unittest.main()
