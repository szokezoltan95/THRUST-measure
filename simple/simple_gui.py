from __future__ import annotations

import tkinter as tk
from pathlib import Path

from simple.simple_config import SimpleConfig
from thrust.paths import ASSETS_DIR


class SimpleGUI:
    """Fullscreen Tk scene for the SimPLE flight task."""

    def __init__(self, config: SimpleConfig, *, fullscreen: bool = True, topmost: bool = True) -> None:
        self.config = config
        self.root = tk.Tk()
        self.root.title("SimPLE · 2D Flight")
        self.root.configure(bg="#07111e")
        self.root.attributes("-fullscreen", fullscreen)
        self.root.attributes("-topmost", topmost)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.running = True
        self._photo = None

        self.canvas = tk.Canvas(self.root, bg="#101b29", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.bg_id = None
        self.hud_id = self.canvas.create_text(
            28, 24, anchor="nw", text="SimPLE  ·  2D FLIGHT CONTROL",
            fill="#d7edff", font=("Segoe UI", 20, "bold"),
        )
        self.target_id = self.canvas.create_oval(0, 0, 0, 0, fill="#e34e59", outline="#ff98a0", width=4)
        self.copter_id = self.canvas.create_oval(0, 0, 0, 0, fill="#43d5ff", outline="#e5faff", width=3)
        self.direction_id = self.canvas.create_line(0, 0, 0, 0, fill="#ffffff", width=5, arrow=tk.LAST)
        self.status_id = self.canvas.create_text(
            28, 60, anchor="nw", text="", fill="#a8bfd3", font=("Segoe UI", 14),
        )
        self.prompt_id = self.canvas.create_text(
            0, 0, anchor="center", text="", fill="#ff6b73", font=("Segoe UI", 30, "bold"),
        )
        self.zone_color("red")
        self.root.update_idletasks()
        self._load_background()
        self.root.bind("<Escape>", lambda _event: self.close())
        self.root.bind("<Configure>", self._redraw_background)
        self.update_status(0, 0, 0.0)
        self._place_prompt()
        self.root.update()

    def _load_background(self) -> None:
        source = Path(ASSETS_DIR) / "simple_background.png"
        if not source.is_file():
            return
        try:
            from PIL import Image, ImageTk
            image = Image.open(source).convert("RGB")
            self._source_image = image
            self._redraw_background()
        except Exception:
            self._source_image = None

    def _redraw_background(self, _event=None) -> None:
        if not hasattr(self, "_source_image"):
            return
        try:
            from PIL import Image, ImageTk
            width = max(1, self.canvas.winfo_width())
            height = max(1, self.canvas.winfo_height())
            image = self._source_image.resize((width, height), Image.Resampling.LANCZOS)
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
        scale = min(width / self.config.field_width_px, height / self.config.field_height_px)
        origin_x = width / 2
        ground_y = height - max(70, height * 0.08)
        return origin_x, ground_y, scale

    def _screen(self, x_m: float, y_m: float) -> tuple[float, float]:
        origin_x, ground_y, scale = self._origin()
        return origin_x + x_m * self.config.zoom_px_per_m * scale, ground_y - y_m * self.config.zoom_px_per_m * scale

    def _place_prompt(self) -> None:
        self.canvas.coords(self.prompt_id, self.canvas.winfo_width() / 2, self.canvas.winfo_height() * 0.82)

    def update_target(self, target: tuple[float, float]) -> None:
        x, y = self._screen(*target)
        radius = self.config.target_zone_radius_px * self._origin()[2]
        self.canvas.coords(self.target_id, x - radius, y - radius, x + radius, y + radius)

    def update_copter(self, position: tuple[float, float], angle_rad: float) -> None:
        x, y = self._screen(*position)
        radius = max(9, self._origin()[2] * 25)
        self.canvas.coords(self.copter_id, x - radius, y - radius, x + radius, y + radius)
        self.canvas.coords(
            self.direction_id, x, y,
            x + radius * 2.2 * __import__("math").sin(angle_rad),
            y - radius * 2.2 * __import__("math").cos(angle_rad),
        )

    def zone_color(self, state: str) -> None:
        color = "#44cf88" if state == "green" else "#e34e59"
        self.canvas.itemconfigure(self.target_id, fill=color, outline="#caffdf" if state == "green" else "#ff98a0")

    def update_status(self, actions: int, resets: int, elapsed_s: float) -> None:
        self.canvas.itemconfigure(
            self.status_id,
            text=f"COMPLETED  {actions:03d}     RESETS  {resets:02d}     ELAPSED  {elapsed_s:0.1f} s",
        )

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
