"""TX16S MK3 EdgeTX LED feedback over the joystick HID Feature report.

Legacy color commands still use the original eight-byte firmware payload.
HIDAPI writes the descriptor-sized 80-byte payload, with report ID 0 prepended
on the host. Target tracking uses command 4 to update all 26 RGB LEDs in one
complete frame.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

VID, PID = 0x1209, 0x4F54
LED_COUNT = 26
FRAME_PAYLOAD_SIZE = 2 + LED_COUNT * 3
REPORT_ID = 0
PROTOCOL_VERSION = 1
COMMAND_SET_COLOR = 1
COMMAND_RELEASE = 2
COMMAND_SET_FRAME = 4
TARGET_GIMBAL_RINGS = 0
TARGET_ALL = 2

MODE_STATIC = "static"
MODE_TARGET_TRACKING = "target_tracking"
MODES = (MODE_STATIC, MODE_TARGET_TRACKING)
STATES = ("idle", "ready", "countdown", "out_of_zone", "in_zone")
TRACKING_STATES = frozenset(("out_of_zone", "in_zone"))
DEFAULTS = {
    "idle": ("#234A80", "pulse"),
    "ready": ("#18A558", "solid"),
    "countdown": ("#E5A100", "blink"),
    "out_of_zone": ("#C83F45", "solid"),
    "in_zone": ("#18A558", "solid"),
}
ANIMATIONS = ("solid", "pulse", "blink")

# Physical indices verified on the user's TX16S MK3.
LEFT_RING = (19, 18, 17, 16, 25, 24, 23, 22, 21, 20)  # L0..L9 clockwise
RIGHT_RING = (9, 10, 11, 12, 13, 14, 15, 6, 7, 8)  # R0..R9 clockwise
BUTTON_LEDS = (0, 1, 2, 3, 4, 5)
BLACK = (0, 0, 0)


@dataclass(frozen=True)
class LedStyle:
    color: str
    animation: str

    def __post_init__(self) -> None:
        if len(self.color) != 7 or self.color[0] != "#":
            raise ValueError("LED color must be #RRGGBB")
        bytes.fromhex(self.color[1:])
        if self.animation not in ANIMATIONS:
            raise ValueError("Unknown LED animation")


def report(command: int, rgb: tuple[int, int, int] = BLACK,
           target: int = TARGET_GIMBAL_RINGS) -> bytes:
    """Return a HIDAPI buffer for an 8-byte legacy command, padded to 80 bytes."""
    payload = bytes((PROTOCOL_VERSION, command, target, *rgb, 0, 0))
    return bytes((REPORT_ID,)) + payload + bytes(FRAME_PAYLOAD_SIZE - len(payload))


def frame_report(colors: dict[int, tuple[int, int, int]]) -> bytes:
    """Return a complete command-4 frame for all 26 physical LEDs."""
    payload = bytearray((PROTOCOL_VERSION, COMMAND_SET_FRAME))
    for index in range(LED_COUNT):
        payload.extend(colors.get(index, BLACK))
    if len(payload) != FRAME_PAYLOAD_SIZE:
        raise AssertionError("Invalid TX16S MK3 LED frame size")
    return bytes((REPORT_ID,)) + bytes(payload)


def brightness(animation: str, elapsed: float) -> float:
    if animation == "pulse":
        return 0.25 + 0.75 * (1 - math.cos(2 * math.pi * elapsed / 1.8)) / 2
    if animation == "blink":
        return 1.0 if elapsed % 0.7 < 0.35 else 0.0
    return 1.0


def color_at(style: LedStyle, elapsed: float) -> tuple[int, int, int]:
    intensity = brightness(style.animation, elapsed)
    return tuple(round(int(style.color[i:i + 2], 16) * intensity) for i in (1, 3, 5))


def proximity_color(progress: float) -> tuple[int, int, int]:
    """Blend red -> yellow -> green as the target error approaches zero."""
    progress = max(0.0, min(1.0, progress))
    if progress <= 0.5:
        amount = progress * 2
        return 255, round(255 * amount), 0
    amount = (progress - 0.5) * 2
    return round(255 * (1 - amount)), 255, 0


def _ring_frame(
    ring: tuple[int, ...],
    error: tuple[float, float],
    max_range: float,
    deadzone: tuple[float, float],
) -> dict[int, tuple[int, int, int]]:
    dx, dy = error
    if abs(dx) <= deadzone[0] and abs(dy) <= deadzone[1]:
        progress = 1.0
    else:
        normalized_error = math.hypot(dx / max_range, dy / max_range)
        progress = 1.0 - min(1.0, normalized_error)

    # Positive Y is up. Index 0 is the top LED; indices advance clockwise.
    angle = math.atan2(dx, dy) % (2 * math.pi)
    head = angle * len(ring) / (2 * math.pi)
    radius = progress * (len(ring) / 2)
    color = proximity_color(progress)
    result: dict[int, tuple[int, int, int]] = {}
    for index, led_index in enumerate(ring):
        difference = abs(index - head)
        distance = min(difference, len(ring) - difference)
        level = 1.0 if progress >= 1 else max(0.0, min(1.0, radius + 1.0 - distance))
        result[led_index] = tuple(round(channel * level) for channel in color)
    return result


def target_tracking_frame(
    left_error: tuple[float, float],
    right_error: tuple[float, float],
    max_range: float,
    left_deadzone: tuple[float, float] = (0.0, 0.0),
    right_deadzone: tuple[float, float] = (0.0, 0.0),
) -> dict[int, tuple[int, int, int]]:
    """Map target-minus-current vectors to two independently colored rings."""
    if not math.isfinite(max_range) or max_range <= 0:
        raise ValueError("max_range must be a positive finite number")
    colors = {index: BLACK for index in range(LED_COUNT)}
    colors.update(_ring_frame(LEFT_RING, left_error, max_range, left_deadzone))
    colors.update(_ring_frame(RIGHT_RING, right_error, max_range, right_deadzone))
    return colors


def _is_tx16smk3(item: dict) -> bool:
    name = "".join(character for character in (item.get("product_string") or "").upper()
                   if character.isalnum())
    return "TX16SMK3" in name


class LedController:
    """Independent HID worker; measurement loops publish only their latest state."""

    def __init__(self, styles: dict[str, LedStyle], on_error=None,
                 mode: str = MODE_STATIC, refresh_hz: int = 30) -> None:
        self.styles = styles.copy()
        self.on_error = on_error
        self._state = "idle"
        self._mode = mode if mode in MODES else MODE_STATIC
        self._refresh_hz = max(1, min(200, int(refresh_hz)))
        self._tracking = {
            "left": (0.0, 0.0),
            "right": (0.0, 0.0),
            "max_range": 1.0,
            "left_deadzone": (0.0, 0.0),
            "right_deadzone": (0.0, 0.0),
        }
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="tx16smk3-led")
            self._thread.start()

    def set_state(self, state: str) -> None:
        if state not in STATES:
            raise ValueError(state)
        with self._lock:
            self._state = state

    def set_styles(self, styles: dict[str, LedStyle]) -> None:
        with self._lock:
            self.styles = styles.copy()

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(mode)
        with self._lock:
            self._mode = mode

    def set_refresh_hz(self, refresh_hz: int) -> None:
        with self._lock:
            self._refresh_hz = max(1, min(200, int(refresh_hz)))

    def set_tracking_vectors(
        self,
        left_error: tuple[float, float],
        right_error: tuple[float, float],
        max_range: float,
        left_deadzone: tuple[float, float] = (0.0, 0.0),
        right_deadzone: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        with self._lock:
            self._tracking = {
                "left": tuple(map(float, left_error)),
                "right": tuple(map(float, right_error)),
                "max_range": max(1e-9, float(max_range)),
                "left_deadzone": tuple(map(float, left_deadzone)),
                "right_deadzone": tuple(map(float, right_deadzone)),
            }

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self) -> None:
        try:
            import hid
        except ImportError as exc:
            if self.on_error:
                self.on_error(str(exc))
            return

        device = None
        entered = time.monotonic()
        previous_state = None
        previous_mode = None
        previous_tracking_active = False
        last_rgb = None
        last_sent = 0.0
        try:
            while not self._stop.is_set():
                if device is None:
                    candidates = [item for item in hid.enumerate(VID, PID)
                                  if _is_tx16smk3(item)
                                  and item.get("usage_page") == 0x01
                                  and item.get("usage") in (0x04, 0x05, 0x08)]
                    if not candidates:
                        self._stop.wait(2)
                        continue
                    device = hid.device()
                    device.open_path(candidates[0]["path"])
                    last_rgb = None

                with self._lock:
                    state = self._state
                    style = self.styles[state]
                    mode = self._mode
                    refresh_hz = self._refresh_hz
                    tracking = dict(self._tracking)

                now = time.monotonic()
                if state != previous_state or mode != previous_mode:
                    entered = now
                    previous_state, previous_mode = state, mode
                    last_rgb = None

                tracking_active = mode == MODE_TARGET_TRACKING and state in TRACKING_STATES
                if previous_tracking_active and not tracking_active:
                    # A full frame owns every LED. Clear it before resuming the
                    # legacy ring-only state so button LEDs return to EdgeTX.
                    device.send_feature_report(report(COMMAND_RELEASE, target=TARGET_ALL))
                    last_rgb = None
                if tracking_active:
                    colors = target_tracking_frame(
                        tracking["left"], tracking["right"], tracking["max_range"],
                        tracking["left_deadzone"], tracking["right_deadzone"],
                    )
                    device.send_feature_report(frame_report(colors))
                else:
                    rgb = color_at(style, now - entered)
                    if rgb != last_rgb or now - last_sent >= 2.0:
                        device.send_feature_report(report(COMMAND_SET_COLOR, rgb))
                        last_rgb, last_sent = rgb, now
                previous_tracking_active = tracking_active

                self._stop.wait(1.0 / refresh_hz)
        except (OSError, ValueError) as exc:
            if self.on_error:
                self.on_error(str(exc))
        finally:
            if device is not None:
                try:
                    device.send_feature_report(report(COMMAND_RELEASE, target=TARGET_ALL))
                    device.close()
                except OSError:
                    pass
