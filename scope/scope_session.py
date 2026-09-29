from __future__ import annotations

import calendar
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pygame

from scope.SCoPE_GUI import SCoPE_GUI
from scope.scope_config import ScopeConfig
from scope.scope_metrics import evaluate_step_response
from thrust.raw_compression import compress_raw_log


@dataclass
class ScopeSessionResult:
    logfile_path: str = ""
    evlfile_path: str = ""
    step_path: str = ""
    graph_path: str = ""
    total_completed: int = 0
    total_mistakes: int = 0
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


def find_lines(channel):
    k = (channel[0][1] - channel[1][1]) / (channel[0][0] - channel[1][0])
    q = channel[0][1] - (k * channel[0][0])
    td = -q / k
    tmax = (1 - q) / k
    return td, tmax


def find_t_points(step_path: str | Path, fps: int):
    stepfile = pd.read_csv(step_path, delimiter="\t")
    lx, ly, ry, rx = [[0, 0], [0, 0]], [[0, 0], [0, 0]], [[0, 0], [0, 0]], [[0, 0], [0, 0]]

    i = 0
    while i < len(stepfile) and stepfile["LXMED"].iloc[i] < 0.20:
        i += 1
    lx[0] = [min(i, len(stepfile) - 1) / fps, stepfile["LXMED"].iloc[min(i, len(stepfile) - 1)]]
    while i < len(stepfile) and stepfile["LXMED"].iloc[i] < 0.80:
        i += 1
    lx[1] = [min(i, len(stepfile) - 1) / fps, stepfile["LXMED"].iloc[min(i, len(stepfile) - 1)]]

    i = 0
    while i < len(stepfile) and stepfile["LYMED"].iloc[i] < 0.20:
        i += 1
    ly[0] = [min(i, len(stepfile) - 1) / fps, stepfile["LYMED"].iloc[min(i, len(stepfile) - 1)]]
    while i < len(stepfile) and stepfile["LYMED"].iloc[i] < 0.80:
        i += 1
    ly[1] = [min(i, len(stepfile) - 1) / fps, stepfile["LYMED"].iloc[min(i, len(stepfile) - 1)]]

    i = 0
    while i < len(stepfile) and stepfile["RYMED"].iloc[i] < 0.20:
        i += 1
    ry[0] = [min(i, len(stepfile) - 1) / fps, stepfile["RYMED"].iloc[min(i, len(stepfile) - 1)]]
    while i < len(stepfile) and stepfile["RYMED"].iloc[i] < 0.80:
        i += 1
    ry[1] = [min(i, len(stepfile) - 1) / fps, stepfile["RYMED"].iloc[min(i, len(stepfile) - 1)]]

    i = 0
    while i < len(stepfile) and stepfile["RXMED"].iloc[i] < 0.20:
        i += 1
    rx[0] = [min(i, len(stepfile) - 1) / fps, stepfile["RXMED"].iloc[min(i, len(stepfile) - 1)]]
    while i < len(stepfile) and stepfile["RXMED"].iloc[i] < 0.80:
        i += 1
    rx[1] = [min(i, len(stepfile) - 1) / fps, stepfile["RXMED"].iloc[min(i, len(stepfile) - 1)]]

    return find_lines(lx), find_lines(ly), find_lines(ry), find_lines(rx)


def build_output_paths(config: ScopeConfig):
    now = datetime.now()
    file_datetime = now.strftime("%Y%m%d_%H%M%S")
    date_token = f"{now.year}{calendar.month_abbr[now.month].upper()}{now.day:02d}"

    scope_root = Path(config.output_root)
    scope_base = scope_root / date_token if config.use_dated_subfolders else scope_root

    actions_dir = scope_base / "actions"
    graphs_dir = scope_base / "graphs"
    logs_dir = scope_base / "logs"
    steps_dir = scope_base / "steps"

    for d in (actions_dir, graphs_dir, logs_dir, steps_dir):
        d.mkdir(parents=True, exist_ok=True)

    safe_user = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in config.user.strip())
    profile = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in config.profile_name.strip()) or "default"

    logfile_path = logs_dir / f"SCoPE_log_{safe_user}_{config.difficulty}_{profile}_{file_datetime}.tsv"
    evlfile_path = actions_dir / f"SCoPE_actions_{safe_user}_{config.difficulty}_{profile}_{file_datetime}.txt"
    step_path = steps_dir / f"SCoPE_step_{safe_user}_{config.difficulty}_{profile}_{file_datetime}.txt"
    graph_path = graphs_dir / f"SCoPE_graph_{safe_user}_{config.difficulty}_{profile}_{file_datetime}.pdf"

    return {
        "base_dir": scope_base,
        "logfile_path": logfile_path,
        "evlfile_path": evlfile_path,
        "step_path": step_path,
        "graph_path": graph_path,
    }


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


def open_file_with_os(path: str | Path):
    path = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass


LEGACY_SCOPE_COLUMNS = {"AILE": "LX", "ELEV": "LY", "THRO": "RY", "RUDD": "RX", "AREQ": "LXRQ", "EREQ": "LYRQ", "TREQ": "RYRQ", "RREQ": "RXRQ"}

def normalize_scope_columns(data: pd.DataFrame) -> pd.DataFrame:
    rename = {old: new for old, new in LEGACY_SCOPE_COLUMNS.items() if old in data.columns and new not in data.columns}
    return data.rename(columns=rename)


def can_run_evaluation(logfile_path: Path) -> tuple[bool, str]:
    if not logfile_path.exists():
        return False, "Log file does not exist."

    if logfile_path.stat().st_size < 32:
        return False, "Log file is too small."

    try:
        data = pd.read_csv(logfile_path, sep="\t")
    except Exception as exc:
        return False, f"Failed to read log: {exc}"

    if data.empty:
        return False, "Log file contains no samples."

    data = normalize_scope_columns(data)
    required_cols = {"LX", "LY", "RY", "RX", "LXRQ", "LYRQ", "RYRQ", "RXRQ"}
    missing = required_cols - set(data.columns)
    if missing:
        return False, f"Missing columns: {sorted(missing)}"

    return True, ""


def run_evaluation(
    config: ScopeConfig,
    logfile_path: Path,
    step_path: Path,
    graph_path: Path,
    log_callback=None,
):
    ok, reason = can_run_evaluation(logfile_path)
    if not ok:
        emit_log(config, log_callback, f"Evaluation skipped: {reason}")
        return "", ""

    emit_log(config, log_callback, f"Evaluating step response from data: {logfile_path}")
    datafile = normalize_scope_columns(pd.read_csv(logfile_path, sep="\t"))

    try:
        emit_log(config, log_callback, "Calculating channel LX...", debug=True)
        step_lx, step_lx_median, step_lx_mean, step_lx_std = evaluate_step_response(
            datafile, "LX", "LXRQ", sampling_hz=config.fps
        )
        emit_log(config, log_callback, "LX evaluation complete.", debug=True)

        emit_log(config, log_callback, "Calculating channel LY...", debug=True)
        step_ly, step_ly_median, step_ly_mean, step_ly_std = evaluate_step_response(
            datafile, "LY", "LYRQ", sampling_hz=config.fps
        )
        emit_log(config, log_callback, "LY evaluation complete.", debug=True)

        emit_log(config, log_callback, "Calculating channel RY...", debug=True)
        step_ry, step_ry_median, step_ry_mean, step_ry_std = evaluate_step_response(
            datafile, "RY", "RYRQ", sampling_hz=config.fps
        )
        emit_log(config, log_callback, "RY evaluation complete.", debug=True)

        emit_log(config, log_callback, "Calculating channel RX...", debug=True)
        step_rx, step_rx_median, step_rx_mean, step_rx_std = evaluate_step_response(
            datafile, "RX", "RXRQ", sampling_hz=config.fps
        )
        emit_log(config, log_callback, "RX evaluation complete.", debug=True)

    except Exception as exc:
        emit_log(config, log_callback, f"Evaluation failed: {exc}")
        return "", ""

    sample_limit = min(
        200,
        len(step_lx_mean),
        len(step_lx_median),
        len(step_lx_std),
        len(step_ly_mean),
        len(step_ly_median),
        len(step_ly_std),
        len(step_ry_mean),
        len(step_ry_median),
        len(step_ry_std),
        len(step_rx_mean),
        len(step_rx_median),
        len(step_rx_std),
    )

    if sample_limit < 10:
        emit_log(config, log_callback, "Evaluation skipped: not enough step samples.")
        return "", ""

    result_step_path = ""
    result_graph_path = ""

    if config.save_step_file:
        emit_log(config, log_callback, f"Saving step response data to file: {step_path}", debug=True)
        stmap = (
            "Time[s]",
            "LXMEA", "LXMED", "LXSTD",
            "LYMEA", "LYMED", "LYSTD",
            "RYMEA", "RYMED", "RYSTD",
            "RXMEA", "RXMED", "RXSTD",
        )

        with open(step_path, "w", encoding="utf-8", newline="") as stepfile:
            csvdump = [
                [i / config.fps for i in range(sample_limit)],
                step_lx_mean[:sample_limit],
                step_lx_median[:sample_limit],
                step_lx_std[:sample_limit],
                step_ly_mean[:sample_limit],
                step_ly_median[:sample_limit],
                step_ly_std[:sample_limit],
                step_ry_mean[:sample_limit],
                step_ry_median[:sample_limit],
                step_ry_std[:sample_limit],
                step_rx_mean[:sample_limit],
                step_rx_median[:sample_limit],
                step_rx_std[:sample_limit],
            ]

            stepfile.write("\t".join(stmap) + "\n")
            for i in range(sample_limit):
                row = [str(seq[i]) for seq in csvdump]
                stepfile.write("\t".join(row) + "\n")

        result_step_path = str(step_path)
        emit_log(config, log_callback, "Step response data saved.", debug=True)

    td_avg = None
    tmax_avg = None
    if config.save_step_file and step_path.exists():
        try:
            a, e, t, r = find_t_points(step_path, config.fps)
            td_avg = (a[0] + e[0] + t[0] + r[0]) / 4
            tmax_avg = (a[1] + e[1] + t[1] + r[1]) / 4
        except Exception:
            td_avg = None
            tmax_avg = None

    emit_log(config, log_callback, "Plotting step response graphs...", debug=True)
    fig = plt.figure(figsize=(15, 10))
    ax1 = plt.subplot2grid((2, 2), (0, 0))
    ax2 = plt.subplot2grid((2, 2), (0, 1))
    ax4 = plt.subplot2grid((2, 2), (1, 0))
    ax3 = plt.subplot2grid((2, 2), (1, 1))

    if td_avg is not None and tmax_avg is not None:
        fig.suptitle(f"{config.user}_{config.difficulty}_Td={td_avg:.3f}_Tmax={tmax_avg:.3f}")
    else:
        fig.suptitle(f"{config.user}_{config.difficulty}")

    x1 = [i / config.fps for i in range(0, len(step_lx_mean))]
    ax1.plot(x1, step_lx_median, color="blue", label="Median")
    ax1.plot(x1, step_lx_mean, color="red", label="Mean")
    ax1.fill_between(
        x1,
        step_lx_mean - step_lx_std,
        step_lx_mean + step_lx_std,
        color="red",
        label="Stdev",
        alpha=0.3,
    )
    ax1.set_xlim(0, 2)
    ax1.set_ylim(-0.2, 1.3)
    ax1.legend(loc="lower right")
    ax1.grid()
    ax1.set_ylabel("Step response")
    ax1.set_xlabel("Time [s]")
    ax1.set_title("LX")

    x2 = [i / config.fps for i in range(0, len(step_ly_mean))]
    ax2.plot(x2, step_ly_median, color="blue", label="Median")
    ax2.plot(x2, step_ly_mean, color="red", label="Mean")
    ax2.fill_between(
        x2,
        step_ly_mean - step_ly_std,
        step_ly_mean + step_ly_std,
        color="red",
        label="Stdev",
        alpha=0.3,
    )
    ax2.set_xlim(0, 2)
    ax2.set_ylim(-0.2, 1.3)
    ax2.legend(loc="lower right")
    ax2.grid()
    ax2.set_ylabel("Step response")
    ax2.set_xlabel("Time [s]")
    ax2.set_title("LY")

    x3 = [i / config.fps for i in range(0, len(step_ry_mean))]
    ax3.plot(x3, step_ry_median, color="blue", label="Median")
    ax3.plot(x3, step_ry_mean, color="red", label="Mean")
    ax3.fill_between(
        x3,
        step_ry_mean - step_ry_std,
        step_ry_mean + step_ry_std,
        color="red",
        label="Stdev",
        alpha=0.3,
    )
    ax3.set_xlim(0, 2)
    ax3.set_ylim(-0.2, 1.3)
    ax3.legend(loc="lower right")
    ax3.grid()
    ax3.set_ylabel("Step response")
    ax3.set_xlabel("Time [s]")
    ax3.set_title("RY")

    x4 = [i / config.fps for i in range(0, len(step_rx_mean))]
    ax4.plot(x4, step_rx_median, color="blue", label="Median")
    ax4.plot(x4, step_rx_mean, color="red", label="Mean")
    ax4.fill_between(
        x4,
        step_rx_mean - step_rx_std,
        step_rx_mean + step_rx_std,
        color="red",
        label="Stdev",
        alpha=0.3,
    )
    ax4.set_xlim(0, 2)
    ax4.set_ylim(-0.2, 1.3)
    ax4.legend(loc="lower right")
    ax4.grid()
    ax4.set_ylabel("Step response")
    ax4.set_xlabel("Time [s]")
    ax4.set_title("RX")

    plt.tight_layout()

    if config.save_graph_pdf:
        emit_log(config, log_callback, f"Saving graph to: {graph_path}", debug=True)
        plt.savefig(graph_path, dpi=300, bbox_inches="tight")
        result_graph_path = str(graph_path)

        if config.auto_open_graph:
            open_file_with_os(graph_path)

    if config.show_graph:
        plt.show()
    else:
        plt.close(fig)

    emit_log(config, log_callback, "Step response evaluation finished.")
    return result_step_path, result_graph_path


def run_scope_session(config: ScopeConfig, log_callback=None) -> ScopeSessionResult:
    config.validate()

    emit_log(config, log_callback, "Validating SCoPE configuration...", debug=True)

    chmap = ("LX", "LY", "RY", "RX", "LEVR", "BUTT", "SIDL", "SIDR")
    acmap = ("LXRQ", "LYRQ", "RYRQ", "RXRQ", "IRRS")
    evmap = ("Time[s]", "Action", "Completed?", "Total mistakes")

    action_shuffle = list(range(16))
    deadzone_np = np.array(config.deadzone)
    fps = config.fps
    hold_time_frames = max(1, int(config.hold_time_s * fps))
    action_timeout_ns = int(config.action_timeout_s * 1_000_000_000)
    stick_max = config.stick_max
    actions = build_actions(stick_max)

    emit_log(config, log_callback, "Building output paths...", debug=True)
    paths = build_output_paths(config)
    logfile_path = paths["logfile_path"]
    evlfile_path = paths["evlfile_path"]
    step_path = paths["step_path"]
    graph_path = paths["graph_path"]
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
    evlfile = None

    try:
        emit_log(config, log_callback, f"Initializing joystick index {config.joystick_index}...", debug=True)
        controller = init_controller(config.joystick_index)
        axes = controller.get_numaxes()
        emit_log(config, log_callback, f"Joystick initialized. Axis count: {axes}", debug=True)

        if 0 <= config.break_axis < axes and controller.get_axis(config.break_axis) > 0:
            emit_log(config, log_callback, "Release break axis on RC", debug=True)
        while 0 <= config.break_axis < axes and controller.get_axis(config.break_axis) > 0:
            pygame.event.pump()

        emit_log(config, log_callback, "Starting countdown...")
        gui.set_prompt_visible(True)
        for i in range(config.countdown_s, 0, -1):
            gui.set_prompt_text(str(i))
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                gui.SCoPE_mainwindow.update_idletasks()
                gui.SCoPE_mainwindow.update()
                time.sleep(min(1 / 60, max(0.0, deadline - time.monotonic())))

        gui.set_prompt_visible(False)

        if config.save_raw_log:
            logfile = open(logfile_path, "w", encoding="utf-8", newline="")
            emit_log(config, log_callback, f"Raw log file opened: {logfile_path}", debug=True)

        if config.save_action_log:
            evlfile = open(evlfile_path, "w", encoding="utf-8", newline="")
            emit_log(config, log_callback, f"Action log file opened: {evlfile_path}", debug=True)

        if logfile is not None:
            logfile.write("TIME")
            for item in chmap:
                logfile.write("\t" + item)
            for item in acmap:
                logfile.write("\t" + item)
            logfile.write("\n")

        if evlfile is not None:
            for item in evmap:
                if item == "Action":
                    if config.difficulty == "easy":
                        evlfile.write(item)
                    else:
                        evlfile.write("LXRQ\tLYRQ\tRYRQ\tRXRQ")
                else:
                    evlfile.write(item)
                evlfile.write("\t")
            evlfile.write("\n")

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
        action_request_np = np.array(action_request)

        gui.updateStickZones(action_request)
        gui.set_action_text("Action: " + str(action_request))
        gui.set_counter_text(f"Completed: {total_completed}    Mistakes: {total_mistakes}")

        clk = pygame.time.Clock()
        start_time = time.time_ns()
        action_start = start_time

        while True:
            gui.SCoPE_mainwindow.update_idletasks()
            gui.SCoPE_mainwindow.update()

            clk.tick(fps)
            sample_time = time.time_ns()
            pygame.event.pump()

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
                logfile.write("\t")
                logfile.write(str(in_range))
                logfile.write("\n")

            axvalues_np = np.array(mapped)

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
                action_request_np = np.array(action_request)
                action_start = sample_time

            if not action_completed:
                if all(
                    axvalues_np[0:4] < (action_request_np[0:4] + deadzone_np[0:4])
                ) and all(
                    axvalues_np[0:4] > (action_request_np[0:4] - deadzone_np[0:4])
                ):
                    inzone_timer += 1
                    in_range = 1
                    gui.updateZoneColor(ok_state=True)
                else:
                    inzone_timer = 0
                    in_range = 0
                    gui.updateZoneColor(ok_state=False)

                if inzone_timer >= hold_time_frames:
                    action_completed = True
                    if evlfile is not None:
                        if config.difficulty == "easy":
                            evlstring = (
                                f"{(sample_time - action_start)/1_000_000_000}\t"
                                f"{action_shuffle[shuffle_sequence]}\t1\t{total_mistakes}\n"
                            )
                        else:
                            evlstring = (
                                f"{(sample_time - action_start)/1_000_000_000}\t"
                                f"{action_request[0]}\t{action_request[1]}\t"
                                f"{action_request[2]}\t{action_request[3]}\t1\t{total_mistakes}\n"
                            )
                        evlfile.write(evlstring)

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
                    if evlfile is not None:
                        if config.difficulty == "easy":
                            evlstring = (
                                f"{(sample_time - action_start)/1_000_000_000}\t"
                                f"{action_shuffle[shuffle_sequence]}\t0\t{total_mistakes}\n"
                            )
                        else:
                            evlstring = (
                                f"{(sample_time - action_start)/1_000_000_000}\t"
                                f"{action_request[0]}\t{action_request[1]}\t"
                                f"{action_request[2]}\t{action_request[3]}\t0\t{total_mistakes}\n"
                            )
                        evlfile.write(evlstring)

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

        if evlfile is not None:
            evlfile.close()
            evlfile = None

        if config.save_raw_log and logfile_path.is_file():
            logfile_path = compress_raw_log(logfile_path)
            emit_log(config, log_callback, f"Compressed SCoPE raw log: {logfile_path}")

        try:
            if gui.SCoPE_mainwindow.winfo_exists():
                gui.SCoPE_mainwindow.destroy()
        except Exception:
            pass

        result_step_path = ""
        result_graph_path = ""

        if config.run_evaluation and config.save_raw_log:
            ok_eval, reason = can_run_evaluation(logfile_path)
            if ok_eval:
                result_step_path, result_graph_path = run_evaluation(
                    config,
                    logfile_path,
                    step_path,
                    graph_path,
                    log_callback=log_callback,
                )
            else:
                emit_log(config, log_callback, f"Evaluation skipped: {reason}")
        else:
            emit_log(config, log_callback, "Evaluation skipped by configuration.", debug=True)

        emit_log(
            config,
            log_callback,
            f"Session finished. Completed={total_completed}, Mistakes={total_mistakes}, Aborted={aborted}",
        )

        return ScopeSessionResult(
            logfile_path=str(logfile_path) if config.save_raw_log else "",
            evlfile_path=str(evlfile_path) if config.save_action_log else "",
            step_path=result_step_path,
            graph_path=result_graph_path,
            total_completed=total_completed,
            total_mistakes=total_mistakes,
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
            if evlfile is not None:
                evlfile.close()
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