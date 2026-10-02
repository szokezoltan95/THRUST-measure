"""TX16S MK3 EdgeTX PC feedback over the joystick HID Feature report.

The firmware uses an eight-byte, unnumbered report. HIDAPI needs a leading
zero report ID on the host side, which is not part of the firmware payload.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

VID, PID = 0x1209, 0x4F54
STATES = ("idle", "ready", "countdown", "out_of_zone", "in_zone")
DEFAULTS = {
    "idle": ("#234A80", "pulse"),
    "ready": ("#18A558", "solid"),
    "countdown": ("#E5A100", "blink"),
    "out_of_zone": ("#C83F45", "solid"),
    "in_zone": ("#18A558", "solid"),
}
ANIMATIONS = ("solid", "pulse", "blink")


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


def report(command: int, rgb: tuple[int, int, int] = (0, 0, 0)) -> bytes:
    """HIDAPI buffer: report ID 0, then version, command, target, RGB, reserved."""
    return bytes((0, 1, command, 0, *rgb, 0, 0))


def brightness(animation: str, elapsed: float) -> float:
    if animation == "pulse":
        return 0.25 + 0.75 * (1 - math.cos(2 * math.pi * elapsed / 1.8)) / 2
    if animation == "blink":
        return 1.0 if elapsed % 0.7 < 0.35 else 0.0
    return 1.0


def color_at(style: LedStyle, elapsed: float) -> tuple[int, int, int]:
    intensity = brightness(style.animation, elapsed)
    return tuple(round(int(style.color[i:i + 2], 16) * intensity) for i in (1, 3, 5))


class LedController:
    """Runs independently of the blocking Pygame measurement loops."""

    def __init__(self, styles: dict[str, LedStyle], on_error=None) -> None:
        self.styles = styles.copy()
        self.on_error = on_error
        self._state = "idle"
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
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
        last_rgb = None
        last_sent = 0.0
        entered = time.monotonic()
        old_state = None
        try:
            while not self._stop.is_set():
                if device is None:
                    # The VID/PID belongs to all EdgeTX radios. Check the product
                    # string so we never drive a different model's LEDs.
                    candidates = [item for item in hid.enumerate(VID, PID)
                                  if "TX16SMK3" in (item.get("product_string") or "").upper()
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
                now = time.monotonic()
                if state != old_state:
                    entered = now
                    old_state = state
                    last_rgb = None
                rgb = color_at(style, now - entered)
                if rgb != last_rgb or now - last_sent > 2:
                    device.send_feature_report(report(1, rgb))
                    last_rgb, last_sent = rgb, now
                self._stop.wait(0.07 if style.animation != "solid" else 0.25)
        except (OSError, ValueError) as exc:
            if self.on_error:
                self.on_error(str(exc))
        finally:
            if device is not None:
                try:
                    device.send_feature_report(report(2))
                    device.close()
                except OSError:
                    pass
