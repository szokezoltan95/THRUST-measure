from __future__ import annotations

import pygame


class SCoPE_GUI:
    """Pygame scene for the SCoPE task."""

    def __init__(
        self, gimbal_size=500, stick_zone=200, stick_max=1000, fullscreen=True,
        topmost=True, screen_background="#000000", gimbal_background="#808080",
        stick_outline="#1e2cff", stick_fill="#ffffff", zone_idle_outline="#ff0000",
        zone_idle_fill="#ff0000", zone_ok_outline="#00cc00", zone_ok_fill="#00cc00",
        grid_color="#ffffff", label_color="#ffffff", prompt_color="#ff0000",
        stick_radius=20, stick_outline_width=6, zone_outline_width=8,
        gimbal_border_width=12, gimbal_cross_width=6, **_unused,
    ):
        self.stick_max = stick_max
        self.stick_zone = stick_zone
        self.colors = {
            "background": screen_background, "gimbal": gimbal_background,
            "stick_outline": stick_outline, "stick_fill": stick_fill,
            "zone_idle": zone_idle_outline, "zone_ok": zone_ok_outline,
            "grid": grid_color, "label": label_color, "prompt": prompt_color,
        }
        self.stick_radius = stick_radius
        self.stick_width = stick_outline_width
        self.zone_width = zone_outline_width
        self.border_width = gimbal_border_width
        self.cross_width = gimbal_cross_width
        pygame.display.init()
        pygame.font.init()
        flags = pygame.FULLSCREEN if fullscreen else 0
        self.screen = pygame.display.set_mode((0, 0) if fullscreen else (1280, 720), flags)
        pygame.display.set_caption("SCoPE")
        self.running = True
        self.prompt_text = ""
        self.prompt_visible = True
        self.action_text = ""
        self.counter_text = ""
        self.targets = [0, 0, 0, 0]
        self.sticks = [0, 0, 0, 0]
        self.zone_ok = False
        self._font = pygame.font.SysFont("Segoe UI", 22)
        self._small_font = pygame.font.SysFont("Segoe UI", 17)
        self._large_font = pygame.font.SysFont("Segoe UI", 72, bold=True)
        self._redraw()

    def _redraw(self):
        width, height = self.screen.get_size()
        self.screen.fill(self.colors["background"])
        size = min(height * 0.66, width * 0.38, 500)
        size = max(160, int(size))
        gap = max(30, int(width * 0.035))
        y = int(height * 0.47 - size / 2)
        left_x = int(width / 2 - size - gap / 2)
        right_x = int(width / 2 + gap / 2)
        scale = size / (2 * self.stick_max)
        for origin_x, target_x, target_y, stick_x, stick_y in (
            (left_x, self.targets[0], self.targets[1], self.sticks[0], self.sticks[1]),
            (right_x, self.targets[3], self.targets[2], self.sticks[3], self.sticks[2]),
        ):
            rect = pygame.Rect(origin_x, y, size, size)
            pygame.draw.rect(self.screen, self.colors["gimbal"], rect)
            pygame.draw.rect(self.screen, self.colors["grid"], rect, self.border_width)
            pygame.draw.line(self.screen, self.colors["grid"], rect.midleft, rect.midright, self.cross_width)
            pygame.draw.line(self.screen, self.colors["grid"], rect.midtop, rect.midbottom, self.cross_width)
            cx, cy = rect.center
            zx = cx + target_x * scale
            zy = cy - target_y * scale
            zw = self.stick_zone * scale * 2
            zone_color = self.colors["zone_ok"] if self.zone_ok else self.colors["zone_idle"]
            zone = pygame.Rect(int(zx - zw / 2), int(zy - zw / 2), int(zw), int(zw))
            pygame.draw.ellipse(self.screen, zone_color, zone, max(1, self.zone_width))
            sx = cx + stick_x * scale
            sy = cy - stick_y * scale
            pygame.draw.circle(self.screen, self.colors["stick_fill"], (int(sx), int(sy)), self.stick_radius)
            pygame.draw.circle(self.screen, self.colors["stick_outline"], (int(sx), int(sy)), self.stick_radius, self.stick_width)
        label_y = min(height - 105, y + size + 24)
        for x, label in ((left_x, "Aileron / Elevator"), (right_x, "Throttle / Rudder")):
            self.screen.blit(self._small_font.render(label, True, self.colors["label"]), (x, label_y))
        self.screen.blit(self._font.render(self.action_text, True, self.colors["label"]), (24, 20))
        self.screen.blit(self._font.render(self.counter_text, True, self.colors["label"]), (24, height - 62))
        if self.prompt_visible and self.prompt_text:
            font = self._large_font if self.prompt_text.isdecimal() else self._font
            text = font.render(self.prompt_text, True, self.colors["prompt"])
            self.screen.blit(text, text.get_rect(center=(width / 2, height / 2)))
        pygame.display.flip()

    def pump(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                self.running = False
        if self.running:
            self._redraw()
        return self.running

    def close(self):
        self.running = False
        pygame.display.quit()

    def set_prompt_text(self, text: str):
        self.prompt_text = text

    def set_prompt_visible(self, visible: bool):
        self.prompt_visible = visible

    def set_action_text(self, text: str):
        self.action_text = text

    def set_counter_text(self, text: str):
        self.counter_text = text

    def updateStickZones(self, zone_posxy):
        self.targets = list(zone_posxy[:4])

    def calculateStickPosition(self, stick_axes):
        return list(stick_axes[:4])

    def updateStickPosition(self, stick_posxy):
        self.sticks = list(stick_posxy[:4])

    def updateZoneColor(self, zone_color=None, ok_state=False):
        self.zone_ok = bool(ok_state or zone_color == self.colors["zone_ok"])
