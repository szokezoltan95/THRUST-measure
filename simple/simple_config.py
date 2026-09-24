from __future__ import annotations

from dataclasses import asdict, dataclass
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
    target_y_max_m: float = 2.0
    field_width_px: int = 1920
    field_height_px: int = 1080
    world_width_m: float = 4.5
    zone_idle_fill: str = "#ff3948"
    zone_idle_outline: str = "#ff3948"
    zone_ok_fill: str = "#00cc66"
    zone_ok_outline: str = "#00ff80"
    mass_kg: float = 0.8
    max_thrust_n: float = 16.0
    drag_coefficient: float = 0.3

    @property
    def world_height_m(self) -> float:
        return self.world_width_m * self.field_height_px / self.field_width_px

    def validate(self) -> None:
        if self.action_timeout_s <= 0 or self.hold_time_s <= 0:
            raise ValueError("Action timeout and hold time must be positive.")
        if not 0 <= self.countdown_s <= 60:
            raise ValueError("Countdown must be between 0 and 60 seconds.")
        if self.background_image_id and not re.fullmatch(r"[0-9a-f]{32}", self.background_image_id):
            raise ValueError("The SimPLE background ID is invalid.")
        if self.completion_radius_m <= 0:
            raise ValueError("Completion radius must be positive.")
        if self.target_x_limit_m <= 0 or self.target_y_max_m <= 0:
            raise ValueError("World target limits must be positive.")
        if self.field_width_px < 600 or self.field_height_px < 400 or self.world_width_m <= 0:
            raise ValueError("The SimPLE resolution and world scale must be positive.")
        if self.mass_kg <= 0 or self.max_thrust_n <= 0 or self.drag_coefficient < 0:
            raise ValueError("Physics parameters are outside their valid range.")
        for color in (self.zone_idle_fill, self.zone_idle_outline, self.zone_ok_fill, self.zone_ok_outline):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("Zone colors must be six-digit hex colors.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SimpleConfig":
        if not isinstance(data, dict):
            return cls()
        values = dict(data)
        # Convert the previous independent px/m scale to the equivalent world width.
        if "world_width_m" not in values and values.get("zoom_px_per_m"):
            try:
                values["world_width_m"] = float(values.get("field_width_px", 1500)) / float(values["zoom_px_per_m"])
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        names = cls.__dataclass_fields__.keys()
        config = cls(**{key: value for key, value in values.items() if key in names})
        config.validate()
        return config
