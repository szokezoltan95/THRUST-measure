from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path

from simple.simple_config import SimpleConfig
from thrust.paths import ASSETS_DIR


class SimpleGUI:
    """Fullscreen Tk scene for the SimPLE flight task."""

    def __init__(self, config: SimpleConfig, *, fullscreen: bool = True, topmost: bool = True, background_path: str | Path | None = None) -> None:
        self.config = config
        self.background_path = Path(background_path) if background_path else None
        self.root = tk.Tk()
        self.root.title("SimPLE · 2D Flight")
        self.root.configure(bg="#000000")
        self.root.attributes("-fullscreen", fullscreen)
        self.root.attributes("-topmost", topmost)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.running = True
        self._photo = None

        self.canvas = tk.Canvas(self.root, bg="#8eb8ca", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.bg_id = None
        self.default_ground_id = self.canvas.create_rectangle(0, 0, 1, 1, fill="#536c54", outline="")
        self.default_horizon_id = self.canvas.create_line(0, 0, 1, 1, fill="#e5eee0", width=2)
        self.hud_id = self.canvas.create_text(
            28, 24, anchor="nw", text="SimPLE  ·  2D FLIGHT CONTROL",
            fill="#ffffff", font=("Segoe UI", 20, "bold"),
        )
        self.target_id = self.canvas.create_oval(0, 0, 0, 0, fill="", outline="#ff0000", width=4)
        self.copter_id = self.canvas.create_oval(0, 0, 0, 0, fill="#1e2cff", outline="#1e2cff", width=1)
        self.center_id = self.canvas.create_oval(0, 0, 0, 0, fill="#1e2cff", outline="#ffffff", width=1)
        self.direction_id = self.canvas.create_line(0, 0, 0, 0, fill="#ffffff", width=5, arrow=tk.LAST)
        self.hud_panel_id = self.canvas.create_rectangle(12, 0, 620, 0, fill="#061321", stipple="gray50", outline="#536b80", width=1)
        self.status_id = self.canvas.create_text(
            28, 0, anchor="nw", text="", fill="#eaf2f8", font=("Segoe UI", 12),
        )
        self.prompt_id = self.canvas.create_text(
            28, 0, anchor="nw", text="", fill="#ff6b72", font=("Segoe UI", 18, "bold"),
        )
        self.zone_color("red")
        self.root.update_idletasks()
        self._load_background()
        self.root.bind("<Escape>", lambda _event: self.close())
        self.root.bind("<Configure>", self._redraw_background)
        self.update_status(0, 0, 0, 0.0)
        self._place_prompt()
        # Keep the aircraft visible during arming and the countdown.
        self.root.update()
        self.update_copter((0.0, 0.0), 0.0)
        self.root.update_idletasks()

    def _load_background(self) -> None:
        source = self.background_path
        if source is None or not source.is_file():
            return
        try:
            from PIL import Image, ImageTk
            image = Image.open(source).convert("RGB")
            self._source_image = image
            self._redraw_background()
        except Exception:
            self._source_image = None

    def _redraw_background(self, _event=None) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        horizon = height * 0.82
        self.canvas.coords(self.default_ground_id, 0, horizon, width, height)
        self.canvas.coords(self.default_horizon_id, 0, horizon, width, horizon)
        if not hasattr(self, "_source_image"):
            self._place_prompt()
            self._place_status()
            return
        try:
            from PIL import Image, ImageOps, ImageTk
            width = max(1, self.canvas.winfo_width())
            height = max(1, self.canvas.winfo_height())
            image = ImageOps.fit(self._source_image, (width, height), method=Image.Resampling.LANCZOS)
            self._photo = ImageTk.PhotoImage(image)
            if self.bg_id is None:
                self.bg_id = self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
                self.canvas.tag_lower(self.bg_id)
            else:
                self.canvas.itemconfigure(self.bg_id, image=self._photo)
            self._place_prompt()
        except Exception:
            return

    def _origin(self) -> tuple[float, float, float]:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        origin_x = width / 2
        ground_y = height - max(110, height * 0.14)
        world_height = self.config.world_height_m
        usable_width = max(1, width - 80)
        usable_height = max(1, ground_y - 40)
        scale = min(usable_width / self.config.world_width_m, usable_height / world_height)
        return origin_x, ground_y, scale

    def _screen(self, x_m: float, y_m: float) -> tuple[float, float]:
        origin_x, ground_y, scale = self._origin()
        return origin_x + x_m * scale, ground_y - y_m * scale

    def _place_prompt(self) -> None:
        self._place_status()
        height = max(1, self.canvas.winfo_height())
        self.canvas.coords(self.prompt_id, 28, height - 48)
        self.canvas.coords(self.hud_panel_id, 12, height - 96, min(760, self.canvas.winfo_width() - 12), height - 12)
        self.canvas.tag_raise(self.hud_panel_id)
        self.canvas.tag_raise(self.status_id)
        self.canvas.tag_raise(self.prompt_id)

    def _place_status(self) -> None:
        height = max(1, self.canvas.winfo_height())
        if hasattr(self, "status_id"):
            self.canvas.coords(self.status_id, 28, height - 84)

    def update_target(self, target: tuple[float, float]) -> None:
        x, y = self._screen(*target)
        radius = self.config.completion_radius_m * self._origin()[2]
        self.canvas.coords(self.target_id, x - radius, y - radius, x + radius, y + radius)

    def update_copter(self, position: tuple[float, float], angle_rad: float) -> None:
        x, y = self._screen(*position)
        # _origin now returns pixels per meter; the earlier 25 was a pixel
        # size multiplier for a dimensionless fit scale, so cap the sprite.
        radius = max(10, min(28, self._origin()[2] * 0.07))
        self.canvas.coords(self.copter_id, x - radius, y - radius, x + radius, y + radius)
        self.canvas.coords(self.center_id, x - 3, y - 3, x + 3, y + 3)
        self.canvas.itemconfigure(self.center_id, fill="#1e2cff", outline="#1e2cff")
        self.canvas.coords(
            self.direction_id, x, y,
            x + radius * 2.2 * math.sin(angle_rad),
            y - radius * 2.2 * math.cos(angle_rad),
        )

    def zone_color(self, state: str) -> None:
        fill = self.config.zone_ok_fill if state == "green" else self.config.zone_idle_fill
        outline = self.config.zone_ok_outline if state == "green" else self.config.zone_idle_outline
        self.canvas.itemconfigure(self.target_id, fill=fill, outline=outline)

    def update_status(self, completed: int, timed_out: int, resets: int, elapsed_s: float) -> None:
        self.canvas.itemconfigure(
            self.status_id,
            text=f"COMPLETED  {completed:03d}     TIMEOUTS  {timed_out:03d}     RESETS  {resets:02d}     ELAPSED  {elapsed_s:0.1f} s",
        )
        self._place_prompt()

    def set_prompt(self, text: str) -> None:
        self._place_prompt()
        self.canvas.itemconfigure(self.prompt_id, text=text)

    def pump(self) -> bool:
        if not self.running:
            return False
        try:
            self.root.update_idletasks()
            self.root.update()
        except tk.TclError:
            self.running = False
        return self.running

    def close(self) -> None:
        self.running = False
        try:
            self.root.destroy()
        except tk.TclError:
            pass
