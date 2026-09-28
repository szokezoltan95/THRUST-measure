# -*- coding: utf-8 -*-
from __future__ import annotations


class SCoPE_GUI:
    def __init__(
        self,
        gimbal_size=500,
        stick_zone=200,
        stick_max=1000,
        fullscreen=True,
        topmost=True,
        screen_background="#000000",
        gimbal_background="#808080",
        stick_outline="#1e2cff",
        stick_fill="#ffffff",
        zone_idle_outline="#ff0000",
        zone_idle_fill="#ff0000",
        zone_ok_outline="#00cc00",
        zone_ok_fill="#00cc00",
        grid_color="#ffffff",
        label_color="#ffffff",
        prompt_color="#ff0000",
        stick_radius=20,
        stick_outline_width=6,
        zone_outline_width=8,
        gimbal_border_width=12,
        gimbal_cross_width=6,
        parent=None,
        embedded=False,
    ):
        self.gimbal_size = gimbal_size
        self.stick_zone = [stick_zone, stick_zone, stick_zone, stick_zone]
        self.stick_max = stick_max
        self.gimbal_scaler = gimbal_size / (2 * stick_max)
        self.gimbal_center = gimbal_size / 2
        self.fullscreen = fullscreen
        self.topmost = topmost

        self.screen_background = screen_background
        self.gimbal_background = gimbal_background
        self.stick_outline = stick_outline
        self.stick_fill = stick_fill
        self.zone_idle_outline = zone_idle_outline
        self.zone_idle_fill = zone_idle_fill
        self.zone_ok_outline = zone_ok_outline
        self.zone_ok_fill = zone_ok_fill
        self.grid_color = grid_color
        self.label_color = label_color
        self.prompt_color = prompt_color

        self.stick_radius = stick_radius
        self.stick_outline_width = stick_outline_width
        self.zone_outline_width = zone_outline_width
        self.gimbal_border_width = gimbal_border_width
        self.gimbal_cross_width = gimbal_cross_width

        self.parent = parent
        self.embedded = embedded

        self.action_text = "Action: [0, 0, 0, 0]"
        self.counter_text = "Completed: 0    Mistakes: 0"
        self.prompt_text = "Press button on RC"
        self.prompt_visible = True

        self.createGUI()

    def createGUI(self):
        import tkinter as tk

        if self.embedded:
            if self.parent is None:
                raise ValueError("embedded=True requires parent")
            self.SCoPE_mainwindow = self.parent
        else:
            self.SCoPE_mainwindow = tk.Tk()
            self.SCoPE_mainwindow.attributes("-fullscreen", self.fullscreen)
            self.SCoPE_mainwindow.attributes("-topmost", self.topmost)

        self.SCoPE_mainwindow.configure(background=self.screen_background)

        self.scene = tk.Canvas(
            self.SCoPE_mainwindow,
            bg=self.screen_background,
            highlightthickness=0,
            bd=0,
        )
        self.scene.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.left_gimbal = tk.Canvas(
            self.scene,
            height=self.gimbal_size,
            width=self.gimbal_size,
            bg=self.gimbal_background,
            relief="flat",
            highlightthickness=0,
            bd=0,
        )
        self._draw_gimbal_grid(self.left_gimbal)

        self.left_stick_zone = self.left_gimbal.create_oval(
            self.gimbal_center - int(self.stick_zone[0] * self.gimbal_scaler),
            self.gimbal_center - int(self.stick_zone[1] * self.gimbal_scaler),
            self.gimbal_center + int(self.stick_zone[0] * self.gimbal_scaler),
            self.gimbal_center + int(self.stick_zone[1] * self.gimbal_scaler),
            outline=self.zone_idle_outline,
            width=self.zone_outline_width,
            fill=self.zone_idle_fill,
        )
        self.left_stick = self.left_gimbal.create_oval(
            self.gimbal_center - self.stick_radius,
            self.gimbal_center - self.stick_radius,
            self.gimbal_center + self.stick_radius,
            self.gimbal_center + self.stick_radius,
            outline=self.stick_outline,
            fill=self.stick_fill,
            width=self.stick_outline_width,
        )

        self.right_gimbal = tk.Canvas(
            self.scene,
            height=self.gimbal_size,
            width=self.gimbal_size,
            bg=self.gimbal_background,
            relief="flat",
            highlightthickness=0,
            bd=0,
        )
        self._draw_gimbal_grid(self.right_gimbal)

        self.right_stick_zone = self.right_gimbal.create_oval(
            self.gimbal_center - int(self.stick_zone[3] * self.gimbal_scaler),
            self.gimbal_center - int(self.stick_zone[2] * self.gimbal_scaler),
            self.gimbal_center + int(self.stick_zone[3] * self.gimbal_scaler),
            self.gimbal_center + int(self.stick_zone[2] * self.gimbal_scaler),
            outline=self.zone_idle_outline,
            width=self.zone_outline_width,
            fill=self.zone_idle_fill,
        )
        self.right_stick = self.right_gimbal.create_oval(
            self.gimbal_center - self.stick_radius,
            self.gimbal_center - self.stick_radius,
            self.gimbal_center + self.stick_radius,
            self.gimbal_center + self.stick_radius,
            outline=self.stick_outline,
            fill=self.stick_fill,
            width=self.stick_outline_width,
        )

        self.left_gimbal_window = self.scene.create_window(0, 0, window=self.left_gimbal, anchor="center")
        self.right_gimbal_window = self.scene.create_window(0, 0, window=self.right_gimbal, anchor="center")

        action_font = ("Segoe UI", 14 if self.embedded else 16, "bold")
        counter_font = ("Segoe UI", 12 if self.embedded else 14)
        prompt_font = ("Segoe UI", 24 if self.embedded else 30, "bold")

        self.ribbon_bg = self.scene.create_rectangle(0, 0, 1, 1, fill="#061321", stipple="gray50", outline="#536b80", width=1)
        self.header_bg = self.scene.create_rectangle(12, 12, 160, 64, fill="#061321", stipple="gray50", outline="#536b80", width=1)
        self.title_item = self.scene.create_text(
            28, 24, text="SCoPE",
            fill=self.label_color, font=("Segoe UI", 16 if self.embedded else 20, "bold"),
            anchor="nw",
        )
        self.action_item = self.scene.create_text(
            0, 0,
            text=self.action_text,
            fill=self.label_color,
            font=action_font,
            anchor="nw",
        )
        self.counter_item = self.scene.create_text(
            0, 0,
            text=self.counter_text,
            fill=self.label_color,
            font=counter_font,
            anchor="nw",
        )
        self.prompt_item = self.scene.create_text(
            0, 0,
            text=self.prompt_text,
            fill=self.prompt_color,
            font=prompt_font,
            anchor="center",
        )
        self.countdown_bg = self.scene.create_rectangle(0, 0, 1, 1, fill="#061321", outline="#536b80", width=2, state="hidden")

        self.SCoPE_mainwindow.bind("<Configure>", self._on_resize)
        self._reposition_scene()

        self.SCoPE_mainwindow.update_idletasks()
        self.SCoPE_mainwindow.update()

    def _draw_gimbal_grid(self, canvas):
        gs = self.gimbal_size
        c = self.grid_color
        bw = self.gimbal_border_width
        cw = self.gimbal_cross_width

        canvas.create_line((gs / 5), 0, 0, 0, 0, (gs / 5), fill=c, width=bw)
        canvas.create_line((gs - (gs / 5)), 0, gs, 0, gs, (gs / 5), fill=c, width=bw)
        canvas.create_line((gs / 5), gs, 0, gs, 0, (gs - (gs / 5)), fill=c, width=bw)
        canvas.create_line((gs - (gs / 5)), gs, gs, gs, gs, (gs - (gs / 5)), fill=c, width=bw)

        canvas.create_line((gs / 2), 0, (gs / 2), (gs / 10), fill=c, width=cw)
        canvas.create_line(0, (gs / 2), (gs / 10), (gs / 2), fill=c, width=cw)
        canvas.create_line((gs / 2), gs, (gs / 2), (gs - (gs / 10)), fill=c, width=cw)
        canvas.create_line(gs, (gs / 2), (gs - (gs / 10)), (gs / 2), fill=c, width=cw)

    def _on_resize(self, event=None):
        self._reposition_scene()

    def _reposition_scene(self):
        try:
            w = self.SCoPE_mainwindow.winfo_width()
            h = self.SCoPE_mainwindow.winfo_height()

            ribbon_top = h - (96 if not self.embedded else 68)
            self.scene.coords(self.ribbon_bg, 0, ribbon_top, w, h)
            self.scene.coords(self.left_gimbal_window, w * 0.30, h * 0.45)
            self.scene.coords(self.right_gimbal_window, w * 0.70, h * 0.45)

            self.scene.coords(self.header_bg, 12, 12, 160, 64)
            self.scene.coords(self.title_item, 28, 24)
            self.scene.coords(self.action_item, 28, ribbon_top + 12)
            self.scene.coords(self.counter_item, max(28, w - 240), ribbon_top + 12)
            countdown = self.prompt_visible and self.prompt_text.isdecimal()
            if countdown:
                self.scene.coords(self.prompt_item, w * 0.5, h * 0.5)
                self.scene.itemconfigure(self.prompt_item, font=("Segoe UI", 76 if not self.embedded else 64, "bold"))
                self.scene.coords(self.countdown_bg, w * 0.5 - 84, h * 0.5 - 72, w * 0.5 + 84, h * 0.5 + 72)
            else:
                self.scene.coords(self.prompt_item, w * 0.5, ribbon_top + 58)
                self.scene.itemconfigure(self.prompt_item, font=("Segoe UI", 24 if self.embedded else 30, "bold"))
            self.scene.itemconfigure(self.countdown_bg, state="normal" if countdown else "hidden")
            self.scene.tag_raise(self.ribbon_bg)
            self.scene.tag_raise(self.header_bg)
            self.scene.tag_raise(self.title_item)
            for item in (self.action_item, self.counter_item, self.prompt_item):
                self.scene.tag_raise(item)
            if countdown:
                self.scene.tag_raise(self.countdown_bg)
                self.scene.tag_raise(self.prompt_item)

            self.scene.itemconfigure(self.prompt_item, state="normal" if self.prompt_visible else "hidden")
        except Exception:
            pass

    def set_action_text(self, text: str):
        self.action_text = str(text)
        self.scene.itemconfigure(self.action_item, text=self.action_text)

    def set_counter_text(self, text: str):
        self.counter_text = str(text)
        self.scene.itemconfigure(self.counter_item, text=self.counter_text)

    def set_prompt_text(self, text: str):
        self.prompt_text = str(text)
        self.scene.itemconfigure(self.prompt_item, text=self.prompt_text)
        self._reposition_scene()

    def apply_colors(
        self,
        screen_background=None,
        gimbal_background=None,
        stick_outline=None,
        stick_fill=None,
        zone_idle_outline=None,
        zone_idle_fill=None,
        zone_ok_outline=None,
        zone_ok_fill=None,
        grid_color=None,
        label_color=None,
        prompt_color=None,
    ):
        if screen_background is not None:
            self.screen_background = screen_background
        if gimbal_background is not None:
            self.gimbal_background = gimbal_background
        if stick_outline is not None:
            self.stick_outline = stick_outline
        if stick_fill is not None:
            self.stick_fill = stick_fill
        if zone_idle_outline is not None:
            self.zone_idle_outline = zone_idle_outline
        if zone_idle_fill is not None:
            self.zone_idle_fill = zone_idle_fill
        if zone_ok_outline is not None:
            self.zone_ok_outline = zone_ok_outline
        if zone_ok_fill is not None:
            self.zone_ok_fill = zone_ok_fill
        if grid_color is not None:
            self.grid_color = grid_color
        if label_color is not None:
            self.label_color = label_color
        if prompt_color is not None:
            self.prompt_color = prompt_color

        self.SCoPE_mainwindow.configure(background=self.screen_background)
        self.scene.configure(bg=self.screen_background)
        self.scene.itemconfigure(self.title_item, fill=self.label_color)
        self.scene.itemconfigure(self.action_item, fill=self.label_color)
        self.scene.itemconfigure(self.counter_item, fill=self.label_color)
        self.scene.itemconfigure(self.prompt_item, fill=self.prompt_color)

        self.left_gimbal.configure(bg=self.gimbal_background)
        self.right_gimbal.configure(bg=self.gimbal_background)

        self.left_gimbal.delete("all")
        self.right_gimbal.delete("all")
        self._draw_gimbal_grid(self.left_gimbal)
        self._draw_gimbal_grid(self.right_gimbal)

        self.left_stick_zone = self.left_gimbal.create_oval(
            self.gimbal_center - int(self.stick_zone[0] * self.gimbal_scaler),
            self.gimbal_center - int(self.stick_zone[1] * self.gimbal_scaler),
            self.gimbal_center + int(self.stick_zone[0] * self.gimbal_scaler),
            self.gimbal_center + int(self.stick_zone[1] * self.gimbal_scaler),
            outline=self.zone_idle_outline,
            width=self.zone_outline_width,
            fill=self.zone_idle_fill,
        )
        self.left_stick = self.left_gimbal.create_oval(
            self.gimbal_center - self.stick_radius,
            self.gimbal_center - self.stick_radius,
            self.gimbal_center + self.stick_radius,
            self.gimbal_center + self.stick_radius,
            outline=self.stick_outline,
            fill=self.stick_fill,
            width=self.stick_outline_width,
        )

        self.right_stick_zone = self.right_gimbal.create_oval(
            self.gimbal_center - int(self.stick_zone[3] * self.gimbal_scaler),
            self.gimbal_center - int(self.stick_zone[2] * self.gimbal_scaler),
            self.gimbal_center + int(self.stick_zone[3] * self.gimbal_scaler),
            self.gimbal_center + int(self.stick_zone[2] * self.gimbal_scaler),
            outline=self.zone_idle_outline,
            width=self.zone_outline_width,
            fill=self.zone_idle_fill,
        )
        self.right_stick = self.right_gimbal.create_oval(
            self.gimbal_center - self.stick_radius,
            self.gimbal_center - self.stick_radius,
            self.gimbal_center + self.stick_radius,
            self.gimbal_center + self.stick_radius,
            outline=self.stick_outline,
            fill=self.stick_fill,
            width=self.stick_outline_width,
        )

        self.updateStickPosition(self.calculateStickPosition([0, 0, 0, 0]))
        self._reposition_scene()
        self.SCoPE_mainwindow.update_idletasks()
        self.SCoPE_mainwindow.update()

    def set_prompt_visible(self, visible: bool):
        self.prompt_visible = bool(visible)
        self._reposition_scene()

    def updateStickZones(self, zone_posxy):
        self.left_gimbal.coords(
            self.left_stick_zone,
            int(((zone_posxy[0] + self.stick_max) - self.stick_zone[0]) * self.gimbal_scaler),
            self.gimbal_size - int(((zone_posxy[1] + self.stick_max) - self.stick_zone[1]) * self.gimbal_scaler),
            int(((zone_posxy[0] + self.stick_max) + self.stick_zone[0]) * self.gimbal_scaler),
            self.gimbal_size - int(((zone_posxy[1] + self.stick_max) + self.stick_zone[1]) * self.gimbal_scaler),
        )
        self.right_gimbal.coords(
            self.right_stick_zone,
            int(((zone_posxy[3] + self.stick_max) - self.stick_zone[3]) * self.gimbal_scaler),
            self.gimbal_size - int(((zone_posxy[2] + self.stick_max) - self.stick_zone[2]) * self.gimbal_scaler),
            int(((zone_posxy[3] + self.stick_max) + self.stick_zone[3]) * self.gimbal_scaler),
            self.gimbal_size - int(((zone_posxy[2] + self.stick_max) + self.stick_zone[2]) * self.gimbal_scaler),
        )

    def calculateStickPosition(self, stick_axes):
        sticks_posxy = [0, 0, 0, 0]
        sticks_posxy[0] = int((stick_axes[0] + self.stick_max) * self.gimbal_scaler)
        sticks_posxy[1] = self.gimbal_size - int((stick_axes[1] + self.stick_max) * self.gimbal_scaler)
        sticks_posxy[2] = int((stick_axes[3] + self.stick_max) * self.gimbal_scaler)
        sticks_posxy[3] = self.gimbal_size - int((stick_axes[2] + self.stick_max) * self.gimbal_scaler)
        return sticks_posxy

    def updateStickPosition(self, stick_posxy):
        r = self.stick_radius
        self.left_gimbal.coords(
            self.left_stick,
            stick_posxy[0] - r,
            stick_posxy[1] - r,
            stick_posxy[0] + r,
            stick_posxy[1] + r,
        )
        self.right_gimbal.coords(
            self.right_stick,
            stick_posxy[2] - r,
            stick_posxy[3] - r,
            stick_posxy[2] + r,
            stick_posxy[3] + r,
        )

    def updateZoneColor(self, zone_color=None, ok_state=False):
        if zone_color is not None:
            outline = zone_color
            fill = zone_color
        else:
            if ok_state:
                outline = self.zone_ok_outline
                fill = self.zone_ok_fill
            else:
                outline = self.zone_idle_outline
                fill = self.zone_idle_fill

        self.left_gimbal.itemconfig(self.left_stick_zone, outline=outline, fill=fill)
        self.right_gimbal.itemconfig(self.right_stick_zone, outline=outline, fill=fill)
