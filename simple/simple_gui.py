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
        self.position = (0.0, 0.0)
        self.angle = 0.0
        self.prompt = ""
        self.status = ""
        self.zone = "red"
        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((0, 0) if fullscreen else (1280, 720), pygame.FULLSCREEN if fullscreen else 0)
        pygame.display.set_caption("SimPLE")
        self.font = pygame.font.SysFont("Segoe UI", 22)
        self.small_font = pygame.font.SysFont("Segoe UI", 17)
        self.large_font = pygame.font.SysFont("Segoe UI", 72, bold=True)
        self.background = None
        if background_path:
            try:
                self.background = pygame.image.load(str(background_path)).convert()
            except (pygame.error, OSError):
                self.background = None
        self._redraw()

    def _origin(self) -> tuple[float, float, float]:
        width, height = self.screen.get_size()
        ground_y = height - max(110, height * 0.14)
        scale = min((width - 80) / self.config.world_width_m,
                    (ground_y - 40) / self.config.world_height_m)
        return width / 2, ground_y, scale

    def _screen(self, x_m: float, y_m: float) -> tuple[int, int]:
        origin_x, ground_y, scale = self._origin()
        return round(origin_x + x_m * scale), round(ground_y - y_m * scale)

    def _redraw(self) -> None:
        width, height = self.screen.get_size()
        if self.background is not None:
            self.screen.blit(pygame.transform.smoothscale(self.background, (width, height)), (0, 0))
        else:
            self.screen.fill("#8eb8ca")
            horizon = int(height * 0.82)
            pygame.draw.rect(self.screen, "#536c54", (0, horizon, width, height - horizon))
            pygame.draw.line(self.screen, "#e5eee0", (0, horizon), (width, horizon), 2)
        target_xy = self._screen(*self.target)
        _, _, scale = self._origin()
        radius = max(4, round(self.config.completion_radius_m * scale))
        target_color = self.config.zone_ok_outline if self.zone == "green" else self.config.zone_idle_outline
        fill_color = self.config.zone_ok_fill if self.zone == "green" else self.config.zone_idle_fill
        pygame.draw.circle(self.screen, fill_color, target_xy, radius)
        pygame.draw.circle(self.screen, target_color, target_xy, radius, 4)
        x, y = self._screen(*self.position)
        copter_radius = max(10, min(28, round(scale * 0.07)))
        pygame.draw.circle(self.screen, "#1e2cff", (x, y), copter_radius)
        pygame.draw.circle(self.screen, "#ffffff", (x, y), copter_radius, 2)
        end = (round(x + copter_radius * 2.2 * math.sin(self.angle)),
               round(y - copter_radius * 2.2 * math.cos(self.angle)))
        pygame.draw.line(self.screen, "#ffffff", (x, y), end, 4)
        bar = pygame.Surface((width, 46), pygame.SRCALPHA)
        bar.fill((16, 24, 32, 190))
        self.screen.blit(bar, (0, height - 46))
        self.screen.blit(self.small_font.render(self.status, True, "#eaf2f8"), (22, height - 35))
        if self.prompt:
            font = self.large_font if self.prompt.isdecimal() else self.font
            text = font.render(self.prompt, True, "#ff6b72")
            y_prompt = height / 2 if self.prompt.isdecimal() else 58
            self.screen.blit(text, text.get_rect(center=(width / 2, y_prompt)))
        pygame.display.flip()

    def update_target(self, target: tuple[float, float]) -> None:
        self.target = target

    def update_copter(self, position: tuple[float, float], angle_rad: float) -> None:
        self.position, self.angle = position, angle_rad

    def zone_color(self, state: str) -> None:
        self.zone = state

    def update_status(self, completed: int, timed_out: int, resets: int, elapsed_s: float) -> None:
        self.status = f"COMPLETED  {completed:03d}     TIMEOUTS  {timed_out:03d}     RESETS  {resets:02d}     ELAPSED  {elapsed_s:0.1f} s"

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
