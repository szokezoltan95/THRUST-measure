from __future__ import annotations

import csv
import math
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pygame

from simple.simple_config import SimpleConfig
from simple.simple_gui import SimpleGUI
from thrust.paths import SIMPLE_OUTPUT_DIR
from thrust.raw_compression import compress_raw_log


@dataclass
class SimpleSessionResult:
    logfile_path: str
    started_at: str
    duration_s: float
    completed_actions: int
    timed_out_actions: int
    reset_count: int
    aborted: bool = False


class Copter:
    """Simple two-dimensional thrust, gravity and quadratic-drag model."""

    def __init__(self, config: SimpleConfig) -> None:
        self.mass = config.mass_kg
        self.max_thrust = config.max_thrust_n
        self.drag = config.drag_coefficient
        self.position = [0.0, 0.0]
        self.velocity = [0.0, 0.0]
        self.acceleration = [0.0, 0.0]
        self.angle = 0.0

    def reset(self) -> None:
        self.position[:] = [0.0, 0.0]
        self.velocity[:] = [0.0, 0.0]
        self.acceleration[:] = [0.0, 0.0]
        self.angle = 0.0

    def update(self, dt: float, throttle: float, angle: float) -> None:
        dt = min(max(dt, 0.0), 0.1)
        self.angle = angle
        thrust = min(1.0, max(0.0, throttle)) * self.max_thrust
        ax = math.sin(angle) * thrust / self.mass - self.drag * self.velocity[0] * abs(self.velocity[0])
        ay = math.cos(angle) * thrust / self.mass - 9.81 - self.drag * self.velocity[1] * abs(self.velocity[1])
        self.acceleration[:] = [ax, ay]
        self.velocity[0] += ax * dt
        self.velocity[1] += ay * dt
        self.position[0] += self.velocity[0] * dt
        self.position[1] += self.velocity[1] * dt
        if self.position[1] < 0.0:
            self.position[1] = 0.0
            self.velocity[1] = max(0.0, -self.velocity[1] * 0.35)
            self.velocity[0] *= 0.98


def _safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return value.strip("_")[:64] or "LOCAL"


def _output_path(runtime: dict[str, Any], participant: str, profile: str) -> Path:
    requested_root = str(runtime.get("output_root") or "")
    root = Path(requested_root).expanduser() if requested_root else SIMPLE_OUTPUT_DIR
    if root.name.lower() == "scope":
        root = root.parent / "simple"
    now = datetime.now()
    if runtime.get("use_dated_subfolders", True):
        root = root / f"{now.year}{now.strftime('%b').upper()}{now.day:02d}"
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs / f"SimPLE_{_safe_name(participant)}_{_safe_name(profile)}_{now:%Y%m%d_%H%M%S}.tsv"


def _axis_value(controller, index: int) -> float:
    if 0 <= index < controller.get_numaxes():
        return float(controller.get_axis(index))
    return 0.0


def _active(value: float) -> bool:
    return value > 0.7


def _new_target(config: SimpleConfig, previous: tuple[float, float] | None) -> tuple[float, float]:
    for _ in range(100):
        candidate = (
            random.uniform(-config.target_x_limit_m, config.target_x_limit_m),
            random.uniform(0.1, config.target_y_max_m),
        )
        if previous is None or math.dist(candidate, previous) >= 0.55:
            return candidate
    return 0.0, min(config.target_y_max_m, 1.0)


def run_simple_session(
    config: SimpleConfig,
    runtime: dict[str, Any],
    *,
    participant: str,
    profile_name: str,
    log_callback: Callable[[str], None] | None = None,
) -> SimpleSessionResult:
    config.validate()
    if not pygame.get_init():
        pygame.init()
    if not pygame.joystick.get_init():
        pygame.joystick.init()
    joystick_index = int(runtime.get("joystick_index", 0))
    if joystick_index < 0 or joystick_index >= pygame.joystick.get_count():
        raise RuntimeError("The selected joystick is not available to SimPLE.")
    controller = pygame.joystick.Joystick(joystick_index)
    controller.init()
    axis_map = runtime.get("axis_map", {})
    roll_axis = int(axis_map.get("AILE", 0))
    throttle_axis = int(axis_map.get("THRO", 2))
    break_axis = int(runtime.get("break_axis", 5))
    reset_axis = int(runtime.get("reset_axis", 6))
    if max(roll_axis, throttle_axis) >= controller.get_numaxes():
        controller.quit()
        pygame.quit()
        raise RuntimeError("The configured SimPLE control axis is missing on the selected joystick.")

    gui = SimpleGUI(
        config, fullscreen=bool(runtime.get("fullscreen", True)),
        topmost=bool(runtime.get("topmost", True)),
        background_path=runtime.get("background_image_path"),
    )
    copter = Copter(config)
    logfile_path = _output_path(runtime, participant, profile_name)
    started = datetime.now(timezone.utc)
    started_clock = pygame.time.get_ticks()
    started_monotonic = time.monotonic()
    clock = pygame.time.Clock()
    completed = timed_out = reset_count = samples = 0
    was_reset = False
    target = _new_target(config, None)
    target_started = pygame.time.get_ticks() / 1000.0
    in_zone_s = 0.0
    aborted = False
    if log_callback:
        log_callback(f"SimPLE runtime initialized on joystick {joystick_index}: {controller.get_name()}.")
        log_callback(f"Writing SimPLE raw samples to {logfile_path}")
    gui.update_target(target)
    gui.set_prompt("RELEASE BREAK TO BEGIN")
    try:
        with logfile_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(("Time[s]", "POSX", "POSY", "REQX", "REQY", "IN_ZONE", "ACTION", "RESET", "ROLL", "THROTTLE"))
            pygame.event.pump()
            while gui.pump() and _active(_axis_value(controller, break_axis)):
                clock.tick(30)
                pygame.event.pump()
            if not gui.running:
                aborted = True
            for count in range(config.countdown_s, 0, -1):
                if aborted or not gui.pump():
                    aborted = True
                    break
                gui.set_prompt(str(count))
                clock.tick(1)
            gui.set_prompt("")
            last_tick = pygame.time.get_ticks()
            while gui.pump() and not _active(_axis_value(controller, break_axis)):
                dt = clock.tick(100) / 1000.0
                now_ms = pygame.time.get_ticks()
                elapsed_s = (now_ms - started_clock) / 1000.0
                pygame.event.pump()
                roll = _axis_value(controller, roll_axis)
                throttle = (_axis_value(controller, throttle_axis) + 1.0) / 2.0
                reset_active = _active(_axis_value(controller, reset_axis))
                if reset_active:
                    # Holding reset locks the aircraft at the origin until the switch
                    # returns to its released (-1) position.
                    copter.reset()
                    if not was_reset:
                        reset_count += 1
                else:
                    copter.update(dt, throttle, roll * math.radians(90))
                was_reset = reset_active
                distance = math.dist(copter.position, target)
                in_zone = distance <= config.completion_radius_m
                in_zone_s = in_zone_s + dt if in_zone else 0.0
                action_number = completed + timed_out + 1
                writer.writerow((
                    f"{elapsed_s:.6f}", f"{copter.position[0]:.6f}", f"{copter.position[1]:.6f}",
                    f"{target[0]:.6f}", f"{target[1]:.6f}", int(in_zone), action_number,
                    int(reset_active), f"{roll:.6f}", f"{throttle:.6f}",
                ))
                samples += 1
                if samples % 20 == 0:
                    handle.flush()
                gui.update_copter(tuple(copter.position), copter.angle)
                gui.update_target(target)
                gui.zone_color("green" if in_zone else "red")
                gui.update_status(completed, timed_out, reset_count, elapsed_s)
                if in_zone_s >= config.hold_time_s:
                    completed += 1
                    target = _new_target(config, target)
                    target_started = now_ms / 1000.0
                    in_zone_s = 0.0
                    gui.update_target(target)
                elif now_ms / 1000.0 - target_started >= config.action_timeout_s:
                    timed_out += 1
                    target = _new_target(config, target)
                    target_started = now_ms / 1000.0
                    in_zone_s = 0.0
                    gui.update_target(target)
            if not gui.running:
                aborted = True
    finally:
        gui.close()
        try:
            controller.quit()
        finally:
            pygame.joystick.quit()
            pygame.quit()
    logfile_path = compress_raw_log(logfile_path)
    if log_callback:
        log_callback(f"Compressed SimPLE raw log: {logfile_path}")
    duration = max(0.0, time.monotonic() - started_monotonic)
    if log_callback:
        log_callback(f"SimPLE finished: completed={completed}, timed out={timed_out}, resets={reset_count}.")
    return SimpleSessionResult(
        logfile_path=str(logfile_path),
        started_at=started.isoformat(),
        duration_s=duration,
        completed_actions=completed,
        timed_out_actions=timed_out,
        reset_count=reset_count,
        aborted=aborted,
    )
