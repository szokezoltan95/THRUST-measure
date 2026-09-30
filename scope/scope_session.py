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

from scope.SCoPE_GUI import SCoPE_GUI
from scope.scope_config import ScopeConfig
from thrust.raw_compression import compress_raw_log


@dataclass
class ScopeSessionResult:
    logfile_path: str = ""
    started_at: str = ""
    total_completed: int = 0
    total_mistakes: int = 0
    samples: int = 0
    output_dir: str = ""
    aborted: bool = False
    abort_reason: str = ""


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


def build_actions(stick_max: int):
    return (
        [-stick_max, 0, 0, 0],
        [stick_max, 0, 0, 0],
        [0, -stick_max, 0, 0],
        [0, stick_max, 0, 0],
        [0, 0, -stick_max, 0],
        [0, 0, stick_max, 0],
        [0, 0, 0, -stick_max],
        [0, 0, 0, stick_max],
        [-stick_max, -stick_max, 0, 0],
        [stick_max, stick_max, 0, 0],
        [stick_max, -stick_max, 0, 0],
        [-stick_max, stick_max, 0, 0],
        [0, 0, -stick_max, -stick_max],
        [0, 0, stick_max, stick_max],
        [0, 0, stick_max, -stick_max],
        [0, 0, -stick_max, stick_max],
    )


def request_new_action(
    difficulty: str,
    shuffle_sequence: int,
    action_shuffle: list[int],
    actions,
    stick_max: int,
    config: ScopeConfig,
    log_callback=None,
):
    if difficulty == "easy":
        if shuffle_sequence < 15:
            shuffle_sequence += 1
        else:
            shuffle_sequence = 0
            random.shuffle(action_shuffle)
        action_request = actions[action_shuffle[shuffle_sequence]]

    elif difficulty == "medium":
        stick_choice = random.choice([0, 1])
        deflx_choice = random.choice(
            [-stick_max * 0.9, (-stick_max / 2), 0, (stick_max / 2), stick_max * 0.9]
        )
        defly_choice = random.choice(
            [-stick_max * 0.9, (-stick_max / 2), 0, (stick_max / 2), stick_max * 0.9]
        )
        if stick_choice == 0:
            action_request = [deflx_choice, defly_choice, 0, 0]
        else:
            action_request = [0, 0, deflx_choice, defly_choice]

    elif difficulty == "hard":
        lx_choice = random.choice(
            [-stick_max * 0.9, (-stick_max / 2), 0, (stick_max / 2), stick_max * 0.9]
        )
        ly_choice = random.choice(
            [-stick_max * 0.9, (-stick_max / 2), 0, (stick_max / 2), stick_max * 0.9]
        )
        ry_choice = random.choice(
            [-stick_max * 0.9, (-stick_max / 2), 0, (stick_max / 2), stick_max * 0.9]
        )
        rx_choice = random.choice(
            [-stick_max * 0.9, (-stick_max / 2), 0, (stick_max / 2), stick_max * 0.9]
        )
        action_request = [lx_choice, ly_choice, ry_choice, rx_choice]

    elif difficulty == "ultra":
        action_request = [
            random.randint(-stick_max, stick_max),
            random.randint(-stick_max, stick_max),
            random.randint(-stick_max, stick_max),
            random.randint(-stick_max, stick_max),
        ]
    else:
        raise ValueError("Invalid difficulty")

    action_request = [int(v) for v in action_request]
    emit_log(config, log_callback, f"New action requested: {action_request}", debug=True)
    return action_request, shuffle_sequence


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


def run_scope_session(config: ScopeConfig, log_callback=None) -> ScopeSessionResult:
    config.validate()

    emit_log(config, log_callback, "Validating SCoPE configuration...", debug=True)

    chmap = ("LX", "LY", "RY", "RX", "LEVR", "BUTT", "SIDL", "SIDR")
    acmap = ("LXRQ", "LYRQ", "RYRQ", "RXRQ", "IRRS", "ACTION_ID", "IN_RANGE")

    action_shuffle = list(range(16))
    deadzone = config.deadzone
    fps = config.fps
    hold_time_frames = max(1, int(config.hold_time_s * fps))
    action_timeout_ns = int(config.action_timeout_s * 1_000_000_000)
    stick_max = config.stick_max
    actions = build_actions(stick_max)

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
        gui.set_prompt_visible(True)
        for i in range(config.countdown_s, 0, -1):
            gui.set_prompt_text(str(i))
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                gui.pump()
                time.sleep(min(1 / 60, max(0.0, deadline - time.monotonic())))

        gui.set_prompt_visible(False)

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
        action_completed = False
        in_range = 0
        inzone_timer = 0
        shuffle_sequence = 0
        aborted = False
        abort_reason = ""

        if config.seed is None:
            random.seed(time.time_ns())
            emit_log(config, log_callback, "Random seed initialized from current time.", debug=True)
        else:
            random.seed(config.seed)
            emit_log(config, log_callback, f"Random seed set to {config.seed}.", debug=True)

        random.shuffle(action_shuffle)
        action_request, shuffle_sequence = request_new_action(
            config.difficulty,
            shuffle_sequence,
            action_shuffle,
            actions,
            stick_max,
            config,
            log_callback,
        )

        gui.updateStickZones(action_request)
        gui.set_action_text("Action: " + str(action_request))
        gui.set_counter_text(f"Completed: {total_completed}    Mistakes: {total_mistakes}")

        clk = pygame.time.Clock()
        started_at = datetime.now().astimezone().isoformat()
        start_time = time.time_ns()
        action_start = start_time
        sample_count = 0

        while True:
            if not gui.pump():
                aborted = True
                abort_reason = "Measurement window closed."
                break

            clk.tick(fps)
            sample_time = time.time_ns()
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

            if logfile is not None:
                logfile.write(str((sample_time - start_time) / 1_000_000_000))
                for val in extended:
                    logfile.write("\t%+2.2f" % val)
                for val in action_request:
                    logfile.write("\t%+2.2f" % val)
                logfile.write(f"\t{total_completed + total_mistakes + 1}\t{in_range}\n")


            if action_completed:
                action_request, shuffle_sequence = request_new_action(
                    config.difficulty,
                    shuffle_sequence,
                    action_shuffle,
                    actions,
                    stick_max,
                    config,
                    log_callback,
                )
                action_completed = False
                inzone_timer = 0
                gui.updateZoneColor(ok_state=False)
                gui.updateStickZones(action_request)
                gui.set_action_text("Action: " + str(action_request))
                action_start = sample_time

            if not action_completed:
                if all(abs(mapped[i] - action_request[i]) < deadzone[i] for i in range(4)):
                    inzone_timer += 1
                    in_range = 1
                    gui.updateZoneColor(ok_state=True)
                else:
                    inzone_timer = 0
                    in_range = 0
                    gui.updateZoneColor(ok_state=False)

                if inzone_timer >= hold_time_frames:
                    action_completed = True
                    total_completed += 1
                    emit_log(
                        config,
                        log_callback,
                        f"Action completed successfully. Completed={total_completed}, Mistakes={total_mistakes}",
                    )
                    gui.set_counter_text(f"Completed: {total_completed}    Mistakes: {total_mistakes}")

                elif sample_time - action_start >= action_timeout_ns:
                    action_completed = True
                    total_mistakes += 1
                    emit_log(
                        config,
                        log_callback,
                        f"Action timeout. Completed={total_completed}, Mistakes={total_mistakes}",
                    )
                    gui.set_counter_text(f"Completed: {total_completed}    Mistakes: {total_mistakes}")

            gui.updateStickPosition(gui.calculateStickPosition(mapped))

            if 0 <= config.break_axis < axes and controller.get_axis(config.break_axis) > 0:
                aborted = True
                abort_reason = f"Session aborted by break axis {config.break_axis}."
                emit_log(config, log_callback, "Session aborted by user.")
                break

            if total_completed >= config.max_completed_actions:
                break

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
            samples=sample_count,
            output_dir=str(paths["base_dir"]),
            aborted=aborted,
            abort_reason=abort_reason,
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
