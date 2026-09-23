from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SimpleConfig:
    """Test-owned SimPLE parameters; joystick and file locations stay local."""

    sampling_hz: int = 100
    action_timeout_s: float = 5.0
    hold_time_s: float = 1.0
    countdown_s: int = 3
    zoom_px_per_m: float = 500.0
    target_zone_radius_px: float = 100.0
    completion_radius_m: float = 0.1
    target_x_limit_m: float = 1.5
    target_y_max_m: float = 2.0
    field_width_px: int = 1500
    field_height_px: int = 1000
    mass_kg: float = 0.8
    max_thrust_n: float = 16.0
    drag_coefficient: float = 0.3

    def validate(self) -> None:
        if not 20 <= self.sampling_hz <= 500:
            raise ValueError("SimPLE sampling frequency must be between 20 and 500 Hz.")
        if self.action_timeout_s <= 0 or self.hold_time_s <= 0:
            raise ValueError("Action timeout and hold time must be positive.")
        if not 0 <= self.countdown_s <= 60:
            raise ValueError("Countdown must be between 0 and 60 seconds.")
        if self.zoom_px_per_m <= 0 or self.target_zone_radius_px <= 0:
            raise ValueError("Zoom and target zone radius must be positive.")
        if self.completion_radius_m <= 0:
            raise ValueError("Completion radius must be positive.")
        if self.target_x_limit_m <= 0 or self.target_y_max_m <= 0:
            raise ValueError("World target limits must be positive.")
        if self.field_width_px < 600 or self.field_height_px < 400:
            raise ValueError("The SimPLE world must be at least 600 × 400 pixels.")
        if self.mass_kg <= 0 or self.max_thrust_n <= 0 or self.drag_coefficient < 0:
            raise ValueError("Physics parameters are outside their valid range.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SimpleConfig":
        if not isinstance(data, dict):
            return cls()
        names = cls.__dataclass_fields__.keys()
        config = cls(**{key: value for key, value in data.items() if key in names})
        config.validate()
        return config
