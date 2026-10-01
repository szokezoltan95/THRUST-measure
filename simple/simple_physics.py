from __future__ import annotations

import math
import random

from simple.simple_config import SimpleConfig


class Copter:
    """2D rigid disc with solid side and ceiling barriers and a grounded crash state."""

    def __init__(self, config: SimpleConfig) -> None:
        self.config = config
        self.mass = config.mass_kg
        self.max_thrust = config.max_thrust_n
        self.drag = config.drag_coefficient
        self.reset()

    def reset(self) -> None:
        self.position = [0.0, self.config.copter_radius_m]
        self.velocity = [0.0, 0.0]
        self.acceleration = [0.0, 0.0]
        self.angle = 0.0
        self.crashed = False
        self.airborne = False

    def update(self, dt: float, throttle: float, angle: float) -> bool:
        """Advance simulation; return True only for a new collision."""
        dt = min(max(dt, 0.0), 0.1)
        radius = self.config.copter_radius_m
        self.angle = angle if not self.crashed else 0.0
        if self.crashed:
            self.acceleration[:] = [0.0, -9.81]
            self.velocity[0] = 0.0
            self.velocity[1] = min(0.0, self.velocity[1] - 9.81 * dt)
            self.position[1] = max(radius, self.position[1] + self.velocity[1] * dt)
            if self.position[1] == radius:
                self.velocity[1] = 0.0
            return False

        thrust = min(1.0, max(0.0, throttle)) * self.max_thrust
        ax = math.sin(angle) * thrust / self.mass - self.drag * self.velocity[0] * abs(self.velocity[0])
        ay = math.cos(angle) * thrust / self.mass - 9.81 - self.drag * self.velocity[1] * abs(self.velocity[1])
        self.acceleration[:] = [ax, ay]
        self.velocity[0] += ax * dt
        self.velocity[1] += ay * dt
        self.position[0] += self.velocity[0] * dt
        self.position[1] += self.velocity[1] * dt

        half_width = self.config.world_width_m / 2 - radius
        ceiling = self.config.world_height_m - radius
        hit_barrier = abs(self.position[0]) >= half_width or self.position[1] >= ceiling
        self.position[0] = max(-half_width, min(half_width, self.position[0]))
        self.position[1] = min(ceiling, self.position[1])
        if hit_barrier or (self.airborne and self.position[1] <= radius and self.velocity[1] < 0):
            self.position[1] = max(radius, self.position[1])
            self.velocity[:] = [0.0, 0.0]
            self.acceleration[:] = [0.0, 0.0]
            self.crashed = True
            return True
        if self.position[1] <= radius:
            self.position[1] = radius
            self.velocity[1] = max(0.0, self.velocity[1])
            self.velocity[0] *= 0.98
        elif self.position[1] > radius + 0.01:
            self.airborne = True
        return False


class TargetSequence:
    """Bounded random targets or repeated slalom/circuit waypoint patterns."""

    def __init__(self, config: SimpleConfig, rng: random.Random | None = None) -> None:
        self.config = config
        self.rng = rng or random.Random()
        self.index = 0

    def next(self, previous: tuple[float, float] | None = None) -> tuple[float, float]:
        c = self.config
        if c.target_pattern == "random":
            for _ in range(100):
                candidate = (
                    self.rng.uniform(-c.target_x_limit_m, c.target_x_limit_m),
                    self.rng.uniform(c.target_y_min_m, c.target_y_max_m),
                )
                if previous is None or math.dist(candidate, previous) >= min(
                    0.55, (2 * c.target_x_limit_m + c.target_y_max_m - c.target_y_min_m) * 0.35
                ):
                    return candidate
            return candidate
        point = self.index % c.route_points
        lap = self.index // c.route_points
        self.index += 1
        fraction = point / max(1, c.route_points - 1)
        if c.target_pattern == "slalom":
            y = c.target_y_min_m + (fraction if lap % 2 == 0 else 1 - fraction) * (c.target_y_max_m - c.target_y_min_m)
            x = (-1 if (self.index - 1) % 2 == 0 else 1) * c.target_x_limit_m
            return x, y
        phase = 2 * math.pi * point / c.route_points
        return c.target_x_limit_m * math.cos(phase), (
            (c.target_y_min_m + c.target_y_max_m) / 2
            + (c.target_y_max_m - c.target_y_min_m) / 2 * math.sin(phase)
        )
