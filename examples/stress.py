"""Stress test — spinning 3D torus built from terminal components.

Exercises: text, hstack, vstack, zstack, box, table, cond, spacer,
clip_and_pad, display_width, render_diff.

    uv run python examples/stress.py
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import terminal as t

R1 = 1.0
R2 = 2.0
K2 = 5.0
SHADE = ".,-~:;=!*#$@"
COLORS = [
    53,
    54,
    55,
    56,
    57,
    93,
    92,
    91,
    90,
    89,
    125,
    161,
    197,
    203,
    209,
    215,
    221,
    227,
    191,
    155,
    119,
]


@dataclass
class S:
    a: float = 0.0
    b: float = 0.0
    speed: float = 1.0
    paused: bool = False
    show_help: bool = False
    render_time: float = 0.0


class _Torus(t.Component):
    def __init__(self, a: float, b: float) -> None:
        self._a = a
        self._b = b

    def flex_grow_width(self) -> int:
        return 1

    def flex_grow_height(self) -> int:
        return 1

    def render(self, width: int, height: int | None = None) -> list[str]:
        height = height or 20
        grid = [[" "] * width for _ in range(height)]
        zbuf = [[0.0] * width for _ in range(height)]
        k1 = width * K2 * 0.4 / (R1 + R2)
        cos_a, sin_a = math.cos(self._a), math.sin(self._a)
        cos_b, sin_b = math.cos(self._b), math.sin(self._b)

        theta = 0.0
        while theta < 6.28:
            cos_t, sin_t = math.cos(theta), math.sin(theta)
            phi = 0.0
            while phi < 6.28:
                cos_p, sin_p = math.cos(phi), math.sin(phi)
                cx = R2 + R1 * cos_t
                cy = R1 * sin_t
                x = cx * (cos_b * cos_p + sin_a * sin_b * sin_p) - cy * cos_a * sin_b
                y = cx * (sin_b * cos_p - sin_a * cos_b * sin_p) + cy * cos_a * cos_b
                z = K2 + cos_a * cx * sin_p + cy * sin_a
                ooz = 1.0 / z
                xp = int(width / 2 + k1 * ooz * x)
                yp = int(height / 2 - k1 * ooz * y * 0.5)
                lum = (
                    cos_p * cos_t * sin_b
                    - cos_a * cos_t * sin_p
                    - sin_a * sin_t
                    + cos_b * (cos_a * sin_t - cos_t * sin_a * sin_p)
                )
                if 0 <= xp < width and 0 <= yp < height and ooz > zbuf[yp][xp]:
                    zbuf[yp][xp] = ooz
                    li = max(0, min(len(SHADE) - 1, int(lum * 8)))
                    ci = max(
                        0,
                        min(len(COLORS) - 1, int((lum + 1) / 2 * (len(COLORS) - 1))),
                    )
                    grid[yp][xp] = f"\033[38;5;{COLORS[ci]}m{SHADE[li]}\033[0m"
                phi += 0.04
            theta += 0.07
        return ["".join(row) for row in grid]


def view(s: S) -> t.Component:
    fps = 1 / s.render_time if s.render_time > 0 else 0
    fps_color = 2 if fps >= 200 else (3 if fps >= 60 else 1)

    scene = t.zstack(
        _Torus(s.a, s.b),
        t.box(
            t.table(
                t.table_row(
                    t.text(t.dim("fps")),
                    t.text(t.bold(t.color(fps_color, f"{fps:5.0f}"))),
                ),
                t.table_row(t.text(t.dim("speed")), t.text(f" {s.speed:.1f}x")),
                spacing=1,
            ),
            padding=1,
        ),
        align="bottom-right",
    )

    if s.show_help:
        scene = t.zstack(
            scene,
            t.box(
                t.vstack(
                    t.text(t.bold("Keyboard shortcuts")),
                    t.text(""),
                    *[
                        t.hstack(
                            t.text(t.bold(t.color(4, k)), padding_right=2),
                            t.text(t.dim(d)),
                        )
                        for k, d in [
                            ("space", "pause / resume"),
                            ("←  →", "adjust speed"),
                            ("r", "reset rotation"),
                            ("?", "toggle this help"),
                            ("q", "quit"),
                        ]
                    ],
                ),
                title="help",
                padding=1,
            ),
            align="center",
        )

    return t.vstack(
        t.hstack(
            t.text(t.bold(t.color(39, "◆ TORUS"))),
            t.cond(s.paused, t.text(t.reverse(t.color(3, " PAUSED ")))),
            t.spacer(),
            t.hstack(
                t.text(t.reverse(t.color(4, " ? "))),
                t.text(t.dim("help")),
                spacing=1,
            ),
            t.hstack(
                t.text(t.reverse(t.color(4, " q "))),
                t.text(t.dim("quit")),
                spacing=1,
            ),
            spacing=1,
        ),
        scene,
    )


if __name__ == "__main__":
    s = S()

    with t.TTY() as term:
        while True:
            # tick
            if not s.paused:
                s.a += 0.04 * s.speed
                s.b += 0.02 * s.speed

            # render
            t0 = time.perf_counter()
            term.screen.render(view(s).render(term.size.columns, term.size.lines))
            s.render_time = time.perf_counter() - t0

            # input (timeout = remaining frame budget @ ~60fps)
            key = term.readkey(max(0, 1 / 60 - s.render_time))
            if key is None or key == "resize":
                continue
            match key:
                case "space":
                    s.paused = not s.paused
                case "right":
                    s.speed = min(5.0, s.speed + 0.5)
                case "left":
                    s.speed = max(0.5, s.speed - 0.5)
                case "r":
                    s.a = s.b = 0.0
                case "?":
                    s.show_help = not s.show_help
                case "q" | "ctrl-q" | "ctrl-d":
                    break
                case _:
                    pass
