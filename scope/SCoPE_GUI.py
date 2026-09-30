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
        self.gimbal_size = gimbal_size
        self.stick_max = stick_max
        self.stick_zone = stick_zone
        self.colors = {
            "background": screen_background, "gimbal": gimbal_background,
            "stick_outline": stick_outline, "stick_fill": stick_fill,
            "zone_idle": zone_idle_outline, "zone_ok": zone_ok_outline,
            "zone_idle_fill": zone_idle_fill, "zone_ok_fill": zone_ok_fill,
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
        size = min(height * 0.66, width * 0.38, self.gimbal_size)
        size = max(160, int(size))
        gap = max(90, int(width * 0.14))
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
            cx, cy = rect.center
            zx = cx + target_x * scale
            zy = cy - target_y * scale
            zw = self.stick_zone * scale * 2
            zone_color = self.colors["zone_ok_fill"] if self.zone_ok else self.colors["zone_idle_fill"]
            zone_outline = self.colors["zone_ok"] if self.zone_ok else self.colors["zone_idle"]
            zone = pygame.Rect(int(zx - zw / 2), int(zy - zw / 2), int(zw), int(zw))
            previous_clip = self.screen.get_clip()
            self.screen.set_clip(rect)
            pygame.draw.ellipse(self.screen, zone_color, zone)
            pygame.draw.ellipse(self.screen, zone_outline, zone, max(1, self.zone_width))
            self.screen.set_clip(previous_clip)
            # The target must remain behind the white guides, including when
            # its edge reaches a corner or side tick.
            self._draw_gimbal_guides(rect)
            sx = cx + stick_x * scale
            sy = cy - stick_y * scale
            pygame.draw.circle(self.screen, self.colors["stick_fill"], (int(sx), int(sy)), self.stick_radius)
            pygame.draw.circle(self.screen, self.colors["stick_outline"], (int(sx), int(sy)), self.stick_radius, self.stick_width)
        self.screen.blit(self._font.render(self.action_text, True, self.colors["label"]), (24, 20))
        self.screen.blit(self._font.render(self.counter_text, True, self.colors["label"]), (24, height - 62))
        if self.prompt_visible and self.prompt_text:
            font = self._large_font if self.prompt_text.isdecimal() else self._font
            text = font.render(self.prompt_text, True, self.colors["prompt"])
            self.screen.blit(text, text.get_rect(center=(width / 2, height / 2)))
        pygame.display.flip()

    def _draw_gimbal_guides(self, rect: pygame.Rect) -> None:
        color = self.colors["grid"]
        width = max(2, min(8, self.border_width // 2))
        tick = max(18, rect.width // 10)
        corner = min(rect.width // 4, tick * 2)
        left, right = rect.left, rect.right - 1
        top, bottom = rect.top, rect.bottom - 1
        for x, y, horizontal_direction, vertical_direction in (
            (left, top, 1, 1), (right, top, -1, 1),
            (left, bottom, 1, -1), (right, bottom, -1, -1),
        ):
            # Keep each stroke inside the gimbal; its outer edge exactly
            # follows the panel boundary. The two filled rectangles overlap
            # in a full width-by-width square for a clean, square joint.
            horizontal = pygame.Rect(
                x if horizontal_direction > 0 else x - corner + 1,
                y if vertical_direction > 0 else y - width + 1,
                corner,
                width,
            )
            vertical = pygame.Rect(
                x if horizontal_direction > 0 else x - width + 1,
                y if vertical_direction > 0 else y - corner + 1,
                width,
                corner,
            )
            pygame.draw.rect(self.screen, color, horizontal)
            pygame.draw.rect(self.screen, color, vertical)

        cx, cy = rect.center
        pygame.draw.line(self.screen, color, (cx, top), (cx, top + tick), self.cross_width)
        pygame.draw.line(self.screen, color, (cx, bottom), (cx, bottom - tick), self.cross_width)
        pygame.draw.line(self.screen, color, (left, cy), (left + tick, cy), self.cross_width)
        pygame.draw.line(self.screen, color, (right, cy), (right - tick, cy), self.cross_width)

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
