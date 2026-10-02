from __future__ import annotations

import csv
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pygame

from simple.simple_config import SimpleConfig
from simple.simple_gui import SimpleGUI
from simple.simple_physics import Copter, TargetSequence
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
    crash_count: int
    samples: int = 0
    aborted: bool = False


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
    return logs / f"THRUST_{_safe_name(participant)}_{_safe_name(profile)}_{now:%Y%m%d_%H%M%S}.tsv"


def _axis_value(controller, index: int) -> float:
    if 0 <= index < controller.get_numaxes():
        return float(controller.get_axis(index))
    return 0.0


def _active(value: float) -> bool:
    return value > 0.7


def run_simple_session(
    config: SimpleConfig,
    runtime: dict[str, Any],
    *,
    participant: str,
    profile_name: str,
    log_callback: Callable[[str], None] | None = None,
    state_callback: Callable[[str], None] | None = None,
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
    roll_axis = int(axis_map.get("LX", 0))
    throttle_axis = int(axis_map.get("RY", 2))
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
    sequence = TargetSequence(config)
    logfile_path = _output_path(runtime, participant, profile_name)
    started = datetime.now(timezone.utc)
    started_clock = pygame.time.get_ticks()
    started_monotonic = time.monotonic()
    clock = pygame.time.Clock()
    completed = timed_out = reset_count = crash_count = samples = 0
    was_reset = False
    target = sequence.next()
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
            writer.writerow(("Time[s]", "POSX", "POSY", "REQX", "REQY", "IN_ZONE", "ACTION", "RESET", "ROLL", "THROTTLE", "CRASH"))
            pygame.event.pump()
            while gui.pump() and _active(_axis_value(controller, break_axis)):
                clock.tick(30)
                pygame.event.pump()
            if not gui.running:
                aborted = True
            if state_callback and not aborted:
                state_callback("countdown")
            for count in range(config.countdown_s, 0, -1):
                if aborted or not gui.pump():
                    aborted = True
                    break
                gui.set_prompt(str(count))
                deadline = time.monotonic() + 1.0
                while time.monotonic() < deadline:
                    if not gui.pump():
                        aborted = True
                        break
                    clock.tick(60)
                if aborted:
                    break
            gui.set_prompt("")
            if state_callback and not aborted:
                state_callback("out_of_zone")
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
                    if copter.update(dt, throttle, roll * math.radians(90)):
                        crash_count += 1
                        if log_callback:
                            log_callback(f"SimPLE collision at {elapsed_s:.2f} s; waiting for reset.")
                was_reset = reset_active
                distance = math.dist(copter.position, target)
                in_zone = not copter.crashed and distance <= config.completion_radius_m
                if state_callback:
                    state_callback("in_zone" if in_zone else "out_of_zone")
                in_zone_s = in_zone_s + dt if in_zone else 0.0
                action_number = completed + timed_out + 1
                writer.writerow((
                    f"{elapsed_s:.6f}", f"{copter.position[0]:.6f}", f"{copter.position[1]:.6f}",
                    f"{target[0]:.6f}", f"{target[1]:.6f}", int(in_zone), action_number,
                    int(reset_active), f"{roll:.6f}", f"{throttle:.6f}", int(copter.crashed),
                ))
                samples += 1
                if samples % 20 == 0:
                    handle.flush()
                gui.update_copter(tuple(copter.position), copter.angle)
                gui.update_target(target)
                gui.zone_color("green" if in_zone else "red")
                gui.update_status(completed, timed_out, reset_count, elapsed_s, crash_count)
                gui.set_prompt("RELEASE RESET" if reset_active else "CRASH · RESET TO CONTINUE" if copter.crashed else "")
                if copter.crashed or reset_active:
                    target_started += dt
                    continue
                if in_zone_s >= config.hold_time_s:
                    completed += 1
                    target = sequence.next(target)
                    target_started = now_ms / 1000.0
                    in_zone_s = 0.0
                    gui.update_target(target)
                elif now_ms / 1000.0 - target_started >= config.action_timeout_s:
                    timed_out += 1
                    target = sequence.next(target)
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
        log_callback(f"SimPLE finished: completed={completed}, timed out={timed_out}, resets={reset_count}, crashes={crash_count}.")
    return SimpleSessionResult(
        logfile_path=str(logfile_path),
        started_at=started.isoformat(),
        duration_s=duration,
        completed_actions=completed,
        timed_out_actions=timed_out,
        reset_count=reset_count,
        crash_count=crash_count,
        samples=samples,
        aborted=aborted,
    )
