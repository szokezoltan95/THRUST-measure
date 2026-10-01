from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any


@dataclass
class SimpleConfig:
    """Test-owned SimPLE parameters; joystick and file locations stay local."""

    action_timeout_s: float = 5.0
    hold_time_s: float = 1.0
    countdown_s: int = 3
    background_image_id: str | None = None
    completion_radius_m: float = 0.1
    target_x_limit_m: float = 1.5
    target_y_min_m: float = 0.25
    target_y_max_m: float = 2.0
    target_pattern: str = "random"
    route_points: int = 6
    field_width_px: int = 1920
    field_height_px: int = 1080
    world_width_m: float = 4.5
    copter_radius_m: float = 0.08
    zone_idle_fill: str = "#ff0000"
    zone_idle_outline: str = "#ff0000"
    zone_ok_fill: str = "#00cc00"
    zone_ok_outline: str = "#00cc00"
    mass_kg: float = 0.8
    max_thrust_n: float = 16.0
    drag_coefficient: float = 0.3

    @property
    def world_height_m(self) -> float:
        return self.world_width_m * self.field_height_px / self.field_width_px

    @property
    def target_margin_m(self) -> float:
        return max(self.copter_radius_m, self.completion_radius_m)

    def validate(self) -> None:
        numeric = (
            self.action_timeout_s, self.hold_time_s, self.completion_radius_m,
            self.target_x_limit_m, self.target_y_min_m, self.target_y_max_m,
            self.world_width_m, self.copter_radius_m, self.mass_kg,
            self.max_thrust_n, self.drag_coefficient,
        )
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in numeric):
            raise ValueError("SimPLE parameters must be finite numbers.")
        if self.action_timeout_s <= 0 or self.hold_time_s <= 0:
            raise ValueError("Action timeout and hold time must be positive.")
        if not isinstance(self.countdown_s, int) or not 0 <= self.countdown_s <= 60:
            raise ValueError("Countdown must be between 0 and 60 seconds.")
        if self.background_image_id and not re.fullmatch(r"[0-9a-f]{32}", self.background_image_id):
            raise ValueError("The SimPLE background ID is invalid.")
        if self.completion_radius_m <= 0 or self.copter_radius_m <= 0:
            raise ValueError("Target and copter radii must be positive.")
        if not isinstance(self.field_width_px, int) or not isinstance(self.field_height_px, int) or self.field_width_px < 600 or self.field_height_px < 400 or self.world_width_m <= 0:
            raise ValueError("The SimPLE resolution and world scale are invalid.")
        margin = self.target_margin_m
        if self.world_width_m <= 2 * margin or self.world_height_m <= 2 * margin:
            raise ValueError("The field must be larger than the copter and target zone.")
        if self.target_x_limit_m <= 0 or self.target_x_limit_m > self.world_width_m / 2 - margin + 1e-9:
            raise ValueError("Horizontal targets must fit inside the field.")
        if self.target_y_min_m < margin - 1e-9 or self.target_y_max_m > self.world_height_m - margin + 1e-9 or self.target_y_min_m > self.target_y_max_m:
            raise ValueError("Target heights must fit between the ground and ceiling.")
        if self.target_pattern not in ("random", "slalom", "circuit"):
            raise ValueError("Unknown SimPLE target trajectory.")
        if not isinstance(self.route_points, int) or not 4 <= self.route_points <= 20:
            raise ValueError("A trajectory needs 4 to 20 target points.")
        if self.mass_kg <= 0 or self.max_thrust_n <= 0 or self.drag_coefficient < 0:
            raise ValueError("Physics parameters are outside their valid range.")
        for color in (self.zone_idle_fill, self.zone_idle_outline, self.zone_ok_fill, self.zone_ok_outline):
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("Zone colors must be six-digit hex colors.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SimpleConfig":
        if not isinstance(data, dict):
            return cls()
        values = dict(data)
        if "world_width_m" not in values and values.get("zoom_px_per_m"):
            try:
                values["world_width_m"] = float(values.get("field_width_px", 1500)) / float(values["zoom_px_per_m"])
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        names = cls.__dataclass_fields__.keys()
        config = cls(**{key: value for key, value in values.items() if key in names})
        config.validate()
        return config
