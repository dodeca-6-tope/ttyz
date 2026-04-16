"""Stress test — spinning 3D torus built from ttyz components.

Exercises: text, hstack, vstack, zstack, box, table, cond, spacer,
clip_and_pad, display_width, render_diff.

    uv run python examples/stress.py
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from _torus import render_torus

import ttyz as t


@dataclass
class S:
    a: float = 0.0
    b: float = 0.0
    speed: float = 1.0
    paused: bool = False
    show_help: bool = False
    render_times: deque[float] = field(default_factory=lambda: deque(maxlen=60))


def _torus(a: float, b: float) -> t.Node:
    def render(width: int, height: int | None = None) -> list[str]:
        return render_torus(a, b, width, height or 20)

    return t.Custom(render, grow=1)


def view(s: S) -> t.Node:
    avg = sum(s.render_times) / len(s.render_times) if s.render_times else 0
    fps = 1 / avg if avg > 0 else 0
    fps_color = 2 if fps >= 200 else (3 if fps >= 60 else 1)

    scene = t.zstack(
        _torus(s.a, s.b),
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
        justify_content="end",
        align_items="end",
        grow=1,
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
            justify_content="center",
            align_items="center",
            grow=1,
        )

    return t.vstack(
        t.hstack(
            t.text(t.bold(t.color(39, "◆ TORUS"))),
            t.cond(s.paused, t.text(t.reverse(t.color(3, " PAUSED ")))),
            t.spacer(),
            t.text(t.reverse(t.color(4, " ? "))),
            t.text(t.dim("help")),
            t.text(t.reverse(t.color(4, " q "))),
            t.text(t.dim("quit")),
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
            term.draw(view(s))
            s.render_times.append(time.perf_counter() - t0)

            # input (timeout = remaining frame budget @ ~60fps)
            event = term.readkey(max(0, 1 / 60 - s.render_times[-1]))
            if event is None or isinstance(event, t.Resize):
                continue
            match event:
                case t.Key(name="space"):
                    s.paused = not s.paused
                case t.Key(name="right"):
                    s.speed = min(5.0, s.speed + 0.5)
                case t.Key(name="left"):
                    s.speed = max(0.5, s.speed - 0.5)
                case t.Key(name="r"):
                    s.a = s.b = 0.0
                case t.Key(name="?"):
                    s.show_help = not s.show_help
                case t.Key(name="q" | "ctrl-q" | "ctrl-d"):
                    break
                case _:
                    pass
