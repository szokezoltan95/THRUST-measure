from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

import pygame

from scope.action_generation import TIMING_SCHEDULE_VERSION, balanced_timing_schedule, generate_next_target
from scope.SCoPE_GUI import SCoPE_GUI
from scope.scope_config import ScopeConfig
from thrust.raw_compression import compress_raw_log


@dataclass
class ScopeSessionResult:
    logfile_path: str = ""
    started_at: str = ""
    total_completed: int = 0
    total_mistakes: int = 0
    total_attempts: int = 0
    samples: int = 0
    output_dir: str = ""
    aborted: bool = False
    abort_reason: str = ""
    timing_schedule_s: list[float] | None = None
    timing_seed: int | None = None
    timing_schedule_version: int = TIMING_SCHEDULE_VERSION


def emit_log(
    config: ScopeConfig,
    log_callback,
    message: str,
    debug: bool = False,
) -> None:
    if log_callback is not None:
        log_callback(message)
    if debug and getattr(config, "debug_output", False):
        print(message)


def build_output_paths(config: ScopeConfig):
    now = datetime.now()
    date_token = f"{now.year}{now.strftime('%b').upper()}{now.day:02d}"
    scope_root = Path(config.output_root)
    scope_base = scope_root / date_token if config.use_dated_subfolders else scope_root
    logs_dir = scope_base / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    safe_user = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in config.user.strip())
    profile = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in config.profile_name.strip()) or "default"
    logfile_path = logs_dir / f"THRUST_{safe_user}_{profile}_{now:%Y%m%d_%H%M%S}.tsv"
    return {"base_dir": scope_base, "logfile_path": logfile_path}


def init_controller(index: int):
    if not pygame.get_init():
        pygame.init()
    if not pygame.joystick.get_init():
        pygame.joystick.init()

    count = pygame.joystick.get_count()
    if count <= 0:
        raise RuntimeError("No joystick detected.")
    if index < 0 or index >= count:
        raise RuntimeError(f"Invalid joystick index {index}. Available: 0..{count - 1}")

    controller = pygame.joystick.Joystick(index)
    controller.init()
    return controller


def run_scope_session(config: ScopeConfig, log_callback=None, state_callback=None) -> ScopeSessionResult:
    config.validate()

    emit_log(config, log_callback, "Validating SCoPE configuration...", debug=True)

    chmap = ("LX", "LY", "RY", "RX", "LEVR", "BUTT", "SIDL", "SIDR")
    acmap = ("LXRQ", "LYRQ", "RYRQ", "RXRQ", "IRRS", "ACTION_ID", "IN_RANGE",
             "LEFT_IN_ZONE", "RIGHT_IN_ZONE", "LEFT_SUCCESS", "RIGHT_SUCCESS",
             "TASK_SUCCESS", "TASK_LIMIT_S", "HOLD_REQUIRED_S", "TASK_ELAPSED_S", "TASK_RESULT")

    deadzone = config.deadzone
    fps = config.fps
    action_timeout_ns = int(config.action_timeout_s * 1_000_000_000)
    stick_max = config.stick_max

    emit_log(config, log_callback, "Building output paths...", debug=True)
    paths = build_output_paths(config)
    logfile_path = paths["logfile_path"]
    emit_log(config, log_callback, f"Output directory: {paths['base_dir']}", debug=True)

    gui = SCoPE_GUI(
        gimbal_size=config.gui_gimbal_size,
        stick_zone=config.gui_stick_zone,
        stick_max=config.stick_max,
        fullscreen=config.fullscreen,
        topmost=config.topmost,
        screen_background=config.screen_background,
        gimbal_background=config.gimbal_background,
        stick_outline=config.stick_outline,
        stick_fill=config.stick_fill,
        zone_idle_outline=config.zone_idle_outline,
        zone_idle_fill=config.zone_idle_fill,
        zone_ok_outline=config.zone_ok_outline,
        zone_ok_fill=config.zone_ok_fill,
        grid_color=config.grid_color,
        label_color=config.label_color,
        prompt_color=config.prompt_color,
        stick_radius=config.gui_stick_radius,
        stick_outline_width=config.gui_stick_outline_width,
        zone_outline_width=config.gui_zone_outline_width,
        gimbal_border_width=config.gui_gimbal_border_width,
        gimbal_cross_width=config.gui_gimbal_cross_width,
    )

    controller = None
    logfile = None

    try:
        emit_log(config, log_callback, f"Initializing joystick index {config.joystick_index}...", debug=True)
        controller = init_controller(config.joystick_index)
        axes = controller.get_numaxes()
        emit_log(config, log_callback, f"Joystick initialized. Axis count: {axes}", debug=True)

        if 0 <= config.break_axis < axes and controller.get_axis(config.break_axis) > 0:
            emit_log(config, log_callback, "Release break axis on RC", debug=True)
        while 0 <= config.break_axis < axes and controller.get_axis(config.break_axis) > 0:
            if not gui.pump():
                raise RuntimeError("Measurement cancelled before recording.")

        emit_log(config, log_callback, "Starting countdown...")
        if state_callback:
            state_callback("countdown")
        gui.set_prompt_visible(True)
        for i in range(config.countdown_s, 0, -1):
            gui.set_prompt_text(str(i))
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                gui.pump()
                time.sleep(min(1 / 60, max(0.0, deadline - time.monotonic())))

        gui.set_prompt_visible(False)
        if state_callback:
            state_callback("out_of_zone")

        logfile = open(logfile_path, "w", encoding="utf-8", newline="")
        emit_log(config, log_callback, f"Raw log file opened: {logfile_path}", debug=True)

        if logfile is not None:
            logfile.write("TIME")
            for item in chmap:
                logfile.write("\t" + item)
            for item in acmap:
                logfile.write("\t" + item)
            logfile.write("\n")


        emit_log(config, log_callback, "Controller link active.")

        total_mistakes = 0
        total_completed = 0
        total_attempts = 0
        action_completed = False
        in_range = 0
        left_in_zone = right_in_zone = 0
        left_success = right_success = task_success = False
        full_since_ns = [None]
        left_since_ns = right_since_ns = None
        aborted = False
        abort_reason = ""

        random_seed = config.seed if config.seed is not None else time.time_ns()
        config.seed = random_seed
        rng = random.Random(random_seed)
        timing_seed = random_seed ^ 0x53434F5045
        timing_rng = random.Random(timing_seed)
        if config.timing_version >= 2:
            if config.timing_mode == "original":
                timing_schedule = balanced_timing_schedule(
                    config.max_completed_actions, config.hold_time_min_s, config.hold_time_max_s, timing_rng
                )
                task_schedule = [5.0] * config.max_completed_actions
            else:
                timing_schedule = balanced_timing_schedule(
                    config.max_completed_actions, config.task_duration_min_s, config.task_duration_max_s, timing_rng
                )
                task_schedule = timing_schedule
        else:
            timing_schedule = [config.hold_time_s] * config.max_completed_actions
            task_schedule = [config.action_timeout_s] * config.max_completed_actions
        emit_log(config, log_callback, f"Target generator seed: {random_seed}.", debug=True)
        action_request = generate_next_target([0, 0, 0, 0], config.action_settings, stick_max, rng)
        emit_log(config, log_callback, f"New target requested: {action_request}", debug=True)

        gui.updateStickZones(action_request)
        gui.set_action_text("Action: " + str(action_request))
        gui.set_counter_text(f"Tasks: 0/{config.max_completed_actions}    Success: 0    Missed: 0")

        clk = pygame.time.Clock()
        started_at = datetime.now().astimezone().isoformat()
        start_time = time.monotonic_ns()
        action_start = start_time
        last_extended = [0] * 8
        current_hold_s = timing_schedule[0]
        current_task_s = task_schedule[0]
        current_action_id = 1
        hold_ns = int((config.success_hold_s if config.timing_version >= 2 and config.timing_mode == "fixed_duration" else current_hold_s) * 1_000_000_000)
        sample_count = 0

        while True:
            if not gui.pump():
                aborted = True
                abort_reason = "Measurement window closed."
                break

            clk.tick(fps)
            sample_time = time.monotonic_ns()
            sample_count += 1

            mapped = [0, 0, 0, 0]
            for i, key in enumerate(("LX", "LY", "RY", "RX")):
                axis_idx = config.axis_map[key]
                if 0 <= axis_idx < axes:
                    mapped[i] = int(controller.get_axis(axis_idx) * stick_max)

            extended = [0] * 8
            extended[0] = mapped[0]
            extended[1] = mapped[1]
            extended[2] = mapped[2]
            extended[3] = mapped[3]

            if axes > 4:
                extended[4] = int(controller.get_axis(4) * stick_max)
            if axes > 5:
                extended[5] = int(controller.get_axis(5) * stick_max)
            if axes > 6:
                extended[6] = int(controller.get_axis(6) * stick_max)
            if axes > 7:
                extended[7] = int(controller.get_axis(7) * stick_max)
            last_extended = extended

            if logfile is not None:
                logfile.write(str((sample_time - start_time) / 1_000_000_000))
                for val in extended:
                    logfile.write("\t%+2.2f" % val)
                for val in action_request:
                    logfile.write("\t%+2.2f" % val)
                logfile.write("\t0")  # Reserved IRRS analysis channel.
                elapsed_task_s = max(0.0, (sample_time - action_start) / 1_000_000_000)
                task_result = 1 if task_success else (2 if action_completed else 0)
                logfile.write(
                    f"\t{current_action_id}\t{in_range}\t{left_in_zone}\t{right_in_zone}"
                    f"\t{int(left_success)}\t{int(right_success)}\t{int(task_success)}"
                    f"\t{current_task_s:.6f}"
                    f"\t{(config.success_hold_s if config.timing_version >= 2 and config.timing_mode == 'fixed_duration' else current_hold_s):.6f}"
                    f"\t{elapsed_task_s:.6f}\t{task_result}\n"
                )


            if action_completed:
                action_request = generate_next_target(action_request, config.action_settings, stick_max, rng)
                emit_log(config, log_callback, f"New target requested: {action_request}", debug=True)
                action_completed = False
                in_range = left_in_zone = right_in_zone = 0
                left_success = right_success = task_success = False
                full_since_ns[0] = left_since_ns = right_since_ns = None
                gui.updateZoneColor(ok_state=False, gimbal_states=(False, False))
                gui.updateStickZones(action_request)
                gui.set_action_text("Action: " + str(action_request))
                action_start = sample_time
                current_action_id += 1
                current_task_index = total_attempts
                if current_task_index < len(timing_schedule):
                    current_hold_s = timing_schedule[current_task_index]
                    current_task_s = task_schedule[current_task_index]
                hold_ns = int((config.success_hold_s if config.timing_version >= 2 and config.timing_mode == "fixed_duration" else current_hold_s) * 1_000_000_000)

            if not action_completed:
                left_in_zone = int(all(abs(mapped[i] - action_request[i]) < deadzone[i] for i in (0, 1)))
                right_in_zone = int(all(abs(mapped[i] - action_request[i]) < deadzone[i] for i in (2, 3)))
                in_range = int(bool(left_in_zone and right_in_zone))
                gui.updateZoneColor(
                    ok_state=bool(in_range),
                    gimbal_states=(bool(left_in_zone), bool(right_in_zone)),
                    independent=config.independent_zone_colors,
                )
                if left_in_zone:
                    left_since_ns = left_since_ns or sample_time
                    if sample_time - left_since_ns >= hold_ns:
                        left_success = True
                else:
                    left_since_ns = None
                if right_in_zone:
                    right_since_ns = right_since_ns or sample_time
                    if sample_time - right_since_ns >= hold_ns:
                        right_success = True
                else:
                    right_since_ns = None
                if in_range:
                    full_since_ns[0] = full_since_ns[0] or sample_time
                else:
                    full_since_ns[0] = None

                if state_callback:
                    state_callback("in_zone" if in_range else "out_of_zone")

                if not task_success and in_range and full_since_ns[0] is not None and sample_time - full_since_ns[0] >= hold_ns:
                    task_success = True
                    total_completed += 1
                    total_attempts += 1
                    if config.timing_version < 2 or config.timing_mode == "original":
                        action_completed = True
                    emit_log(
                        config,
                        log_callback,
                        f"Action completed successfully. Completed={total_completed}, Mistakes={total_mistakes}",
                    )
                    gui.set_counter_text(f"Tasks: {total_attempts}/{config.max_completed_actions}    Success: {total_completed}    Missed: {total_mistakes}")

                if not action_completed and (sample_time - action_start >= (int(current_task_s * 1_000_000_000) if config.timing_version >= 2 else action_timeout_ns)):
                    action_completed = True
                    if not task_success:
                        total_attempts += 1
                        total_mistakes += 1
                        emit_log(
                            config,
                            log_callback,
                            f"Action timeout. Completed={total_completed}, Mistakes={total_mistakes}",
                        )
                    gui.set_counter_text(f"Tasks: {total_attempts}/{config.max_completed_actions}    Success: {total_completed}    Missed: {total_mistakes}")

            gui.updateStickPosition(gui.calculateStickPosition(mapped))

            if (total_attempts >= config.max_completed_actions if config.timing_version >= 2 else total_completed >= config.max_completed_actions):
                break

            if 0 <= config.break_axis < axes and controller.get_axis(config.break_axis) > 0:
                aborted = True
                abort_reason = f"Session aborted by break axis {config.break_axis}."
                emit_log(config, log_callback, "Session aborted by user.")
                break

        session_task_quota_met = (
            total_attempts >= config.max_completed_actions
            if config.timing_version >= 2
            else total_completed >= config.max_completed_actions
        )
        if logfile is not None and sample_count and (aborted or session_task_quota_met):
            interrupt_time = time.monotonic_ns()
            elapsed = max(0.0, (interrupt_time - action_start) / 1_000_000_000)
            task_result = 1 if task_success else (2 if action_completed or session_task_quota_met else 3)
            logfile.write(f"{(interrupt_time - start_time) / 1_000_000_000:.9f}")
            for value in last_extended:
                logfile.write("\t%+2.2f" % value)
            for value in action_request:
                logfile.write("\t%+2.2f" % value)
            logfile.write(
                f"\t0\t{current_action_id}\t{in_range}\t{left_in_zone}\t{right_in_zone}"
                f"\t{int(left_success)}\t{int(right_success)}\t{int(task_success)}"
                f"\t{current_task_s:.6f}"
                f"\t{(config.success_hold_s if config.timing_version >= 2 and config.timing_mode == 'fixed_duration' else current_hold_s):.6f}"
                f"\t{elapsed:.6f}\t{task_result}\n"
            )

        emit_log(config, log_callback, "Controller link closed.")

        if logfile is not None:
            logfile.close()
            logfile = None

        if logfile_path.is_file():
            logfile_path = compress_raw_log(logfile_path)
            emit_log(config, log_callback, f"Compressed SCoPE raw log: {logfile_path}")

        gui.close()
        emit_log(
            config,
            log_callback,
            f"Session finished. Completed={total_completed}, Mistakes={total_mistakes}, Aborted={aborted}",
        )

        return ScopeSessionResult(
            logfile_path=str(logfile_path),
            started_at=started_at,
            total_completed=total_completed,
            total_mistakes=total_mistakes,
            total_attempts=total_attempts,
            samples=sample_count,
            output_dir=str(paths["base_dir"]),
            aborted=aborted,
            abort_reason=abort_reason,
            timing_schedule_s=timing_schedule,
            timing_seed=timing_seed,
            timing_schedule_version=TIMING_SCHEDULE_VERSION,
        )

    finally:
        try:
            if logfile is not None:
                logfile.close()
        except Exception:
            pass
        try:
            if controller is not None:
                controller.quit()
        except Exception:
            pass
        try:
            pygame.joystick.quit()
        except Exception:
            pass
        try:
            pygame.quit()
        except Exception:
            pass
