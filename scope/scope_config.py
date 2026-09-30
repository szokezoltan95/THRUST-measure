from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scope.action_generation import DEFAULT_ACTION_SETTINGS, validate_action_settings


def _default_action_settings() -> dict[str, Any]:
    return {
        **DEFAULT_ACTION_SETTINGS,
        "intervals": {axis: list(bounds) for axis, bounds in DEFAULT_ACTION_SETTINGS["intervals"].items()},
    }


@dataclass
class ScopeConfig:
    # experiment
    debug_output: bool = False
    user: str = "Pilot"
    # Accepted when reading older local configuration files; new tests use
    # action_settings instead of named difficulty branches.
    difficulty: str = "hard"
    action_timeout_s: float = 3.0
    hold_time_s: float = 0.5
    fps: int = 100
    stick_max: int = 1000
    deadzone: list[int] = field(default_factory=lambda: [100, 100, 100, 100])
    max_completed_actions: int = 50
    countdown_s: int = 3
    seed: int | None = None
    action_settings: dict[str, Any] = field(default_factory=_default_action_settings)

    # runtime
    fullscreen: bool = True
    topmost: bool = True
    joystick_index: int = 0
    break_axis: int = 5
    reset_axis: int = 6
    axis_map: dict[str, int] = field(
        default_factory=lambda: {
            "LX": 0,
            "LY": 1,
            "RY": 2,
            "RX": 3,
        }
    )

    # output
    output_root: str = str(Path.home() / "Documents" / "THRUST" / "scope")
    profile_name: str = "default"
    use_dated_subfolders: bool = True

    # launcher / UX
    expert_mode: bool = False

    # GUI geometry
    gui_gimbal_size: int = 500
    gui_stick_zone: int = 200

    # adjustable object sizes
    gui_stick_radius: int = 20
    gui_stick_outline_width: int = 6
    gui_zone_outline_width: int = 8
    gui_gimbal_border_width: int = 12
    gui_gimbal_cross_width: int = 6

    # GUI colors
    screen_background: str = "#000000"
    gimbal_background: str = "#808080"
    stick_outline: str = "#1e2cff"
    stick_fill: str = "#ffffff"
    zone_idle_outline: str = "#ff0000"
    zone_idle_fill: str = "#ff0000"
    zone_ok_outline: str = "#00cc00"
    zone_ok_fill: str = "#00cc00"
    grid_color: str = "#ffffff"
    label_color: str = "#ffffff"
    prompt_color: str = "#ff0000"

    def validate(self) -> None:
        validate_action_settings(self.action_settings)
        if not self.user.strip():
            raise ValueError("User / pilot name cannot be empty")
        if self.fps < 10:
            raise ValueError("FPS must be at least 10")
        if self.stick_max <= 0:
            raise ValueError("stick_max must be positive")
        if self.action_timeout_s <= 0:
            raise ValueError("Action timeout must be positive")
        if self.hold_time_s <= 0:
            raise ValueError("Hold time must be positive")
        if self.max_completed_actions <= 0:
            raise ValueError("Target completed actions must be positive")
        if len(self.deadzone) != 4:
            raise ValueError("Deadzone must contain exactly 4 values")
        if any(v < 0 for v in self.deadzone):
            raise ValueError("Deadzone values must be non-negative")
        if any(v >= self.stick_max for v in self.deadzone):
            raise ValueError("Deadzone values must be smaller than stick_max")

        required = {"LX", "LY", "RY", "RX"}
        if set(self.axis_map.keys()) != required:
            raise ValueError("axis_map must contain LX, LY, RY and RX")

        if self.gui_gimbal_size < 150:
            raise ValueError("gui_gimbal_size must be at least 150")
        if self.gui_stick_zone <= 0:
            raise ValueError("gui_stick_zone must be positive")
        if self.gui_stick_radius <= 0:
            raise ValueError("gui_stick_radius must be positive")
        if self.gui_stick_outline_width <= 0:
            raise ValueError("gui_stick_outline_width must be positive")
        if self.gui_zone_outline_width <= 0:
            raise ValueError("gui_zone_outline_width must be positive")
        if self.gui_gimbal_border_width <= 0:
            raise ValueError("gui_gimbal_border_width must be positive")
        if self.gui_gimbal_cross_width <= 0:
            raise ValueError("gui_gimbal_cross_width must be positive")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("difficulty", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScopeConfig":
        normalized = dict(data)
        incoming_actions = normalized.get("action_settings")
        merged_actions = _default_action_settings()
        if isinstance(incoming_actions, dict):
            merged_actions.update(incoming_actions)
            if isinstance(incoming_actions.get("intervals"), dict):
                merged_actions["intervals"].update(incoming_actions["intervals"])
        normalized["action_settings"] = merged_actions
        axis_map = normalized.get("axis_map")
        if isinstance(axis_map, dict):
            legacy = {"AILE": "LX", "ELEV": "LY", "THRO": "RY", "RUDD": "RX"}
            defaults = {"LX": 0, "LY": 1, "RY": 2, "RX": 3}
            normalized["axis_map"] = {
                name: axis_map.get(name, axis_map.get(old, defaults[name]))
                for name, old in (("LX", "AILE"), ("LY", "ELEV"), ("RY", "THRO"), ("RX", "RUDD"))
            }
        return cls(**normalized)

    def save_json(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)

    @classmethod
    def load_json(cls, path: str | Path) -> "ScopeConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))
