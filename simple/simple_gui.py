from __future__ import annotations

import math
from pathlib import Path

import pygame

from simple.simple_config import SimpleConfig


class SimpleGUI:
    """Pygame scene for the SimPLE flight task."""

    def __init__(self, config: SimpleConfig, *, fullscreen: bool = True, topmost: bool = True,
                 background_path: str | Path | None = None) -> None:
        self.config = config
        self.running = True
        self.target = (0.0, 0.0)
        self.position = (0.0, config.copter_radius_m)
        self.angle = 0.0
        self.prompt = ""
        self.status = ""
        self.zone = "red"
        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((0, 0) if fullscreen else (1280, 720), pygame.FULLSCREEN if fullscreen else 0)
        pygame.display.set_caption("SimPLE")
        self.small_font = pygame.font.SysFont("Segoe UI", 17)
        self.large_font = pygame.font.SysFont("Segoe UI", 72, bold=True)
        self.message_font = pygame.font.SysFont("Segoe UI", 48, bold=True)
        self.background = None
        if background_path:
            try:
                self.background = pygame.image.load(str(background_path)).convert()
            except (pygame.error, OSError):
                self.background = None
        self._redraw()

    def _origin(self) -> tuple[float, float, float]:
        width, height = self.screen.get_size()
        # Keep the collision walls close to the screen edges while reserving
        # the bottom strip for status text and a small gap above it.
        ground_y = height - 50
        scale = min((width - 16) / self.config.world_width_m,
                    (ground_y - 8) / self.config.world_height_m)
        return width / 2, ground_y, scale

    def _screen(self, x_m: float, y_m: float) -> tuple[int, int]:
        origin_x, ground_y, scale = self._origin()
        return round(origin_x + x_m * scale), round(ground_y - y_m * scale)

    def _redraw(self) -> None:
        width, height = self.screen.get_size()
        self.screen.fill("#000000")
        ox, ground_y, scale = self._origin()
        left = round(ox - self.config.world_width_m * scale / 2)
        right = round(ox + self.config.world_width_m * scale / 2)
        top = round(ground_y - self.config.world_height_m * scale)
        field = pygame.Rect(left, top, right - left, round(ground_y) - top)
        if self.background is not None:
            picture = pygame.transform.smoothscale(self.background, (field.width, field.height))
            self.screen.blit(picture, field.topleft)
            veil = pygame.Surface(field.size, pygame.SRCALPHA)
            veil.fill((30, 30, 30, 110))
            self.screen.blit(veil, field.topleft)
        else:
            pygame.draw.rect(self.screen, "#808080", field)
        # The physical collision planes coincide with the inner edges of these lines.
        pygame.draw.lines(self.screen, "#ffffff", False,
                          [(left, round(ground_y)), (left, top), (right, top), (right, round(ground_y))], 4)
        pygame.draw.line(self.screen, "#ffffff", (left, round(ground_y)), (right, round(ground_y)), 5)
        for x in range(left + 12, right, 22):
            pygame.draw.line(self.screen, "#7e7e7e", (x, round(ground_y) + 5),
                             (min(x + 10, right), round(ground_y) + 15), 2)

        target_xy = self._screen(*self.target)
        radius = max(1, round(self.config.completion_radius_m * scale))
        target_color = self.config.zone_ok_outline if self.zone == "green" else self.config.zone_idle_outline
        fill_color = self.config.zone_ok_fill if self.zone == "green" else self.config.zone_idle_fill
        pygame.draw.circle(self.screen, fill_color, target_xy, radius)
        pygame.draw.circle(self.screen, target_color, target_xy, radius, 2)
        x, y = self._screen(*self.position)
        copter_radius = max(1, round(scale * self.config.copter_radius_m))
        pygame.draw.circle(self.screen, "#1e2cff", (x, y), copter_radius)
        pygame.draw.circle(self.screen, "#ffffff", (x, y), copter_radius, 2)
        end = (round(x + copter_radius * 1.8 * math.sin(self.angle)),
               round(y - copter_radius * 1.8 * math.cos(self.angle)))
        pygame.draw.line(self.screen, "#ffffff", (x, y), end, 3)
        bar = pygame.Surface((width, 46), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 220))
        self.screen.blit(bar, (0, height - 46))
        self.screen.blit(self.small_font.render(self.status, True, "#ffffff"), (22, height - 35))
        if self.prompt:
            font = self.large_font if self.prompt.isdecimal() else self.message_font
            rendered = font.render(self.prompt, True, "#ff4c4c")
            max_width = max(1, width - 32)
            if rendered.get_width() > max_width:
                ratio = max_width / rendered.get_width()
                rendered = pygame.transform.smoothscale(
                    rendered, (max_width, max(1, round(rendered.get_height() * ratio))),
                )
            self.screen.blit(rendered, rendered.get_rect(center=(width / 2, (top + ground_y) / 2)))
        pygame.display.flip()

    def update_target(self, target: tuple[float, float]) -> None:
        self.target = target

    def update_copter(self, position: tuple[float, float], angle_rad: float) -> None:
        self.position, self.angle = position, angle_rad

    def zone_color(self, state: str) -> None:
        self.zone = state

    def update_status(self, completed: int, timed_out: int, resets: int, elapsed_s: float, crashes: int = 0) -> None:
        self.status = f"COMPLETED  {completed:03d}     TIMEOUTS  {timed_out:03d}     RESETS  {resets:02d}     CRASHES  {crashes:02d}     ELAPSED  {elapsed_s:0.1f} s"

    def set_prompt(self, text: str) -> None:
        self.prompt = text

    def pump(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                self.running = False
        self._redraw()
        return self.running

    def close(self) -> None:
        self.running = False
        pygame.display.quit()
