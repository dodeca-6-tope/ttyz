from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pytest

from ttyz import Buffer, render_to_buffer

SNAP_DIR = Path(__file__).parent / "snapshots"


class SnapFn(Protocol):
    def __call__(
        self, node: object, w: int, h: int | None = None, *, name: str | None = None
    ) -> None: ...


def render(node: object, w: int, h: int | None = None) -> list[str]:
    bh = h if h is not None else 100
    buf = Buffer(w, bh)
    rows = render_to_buffer(node, buf, h if h is not None else -1)
    return [buf.row_styled(i) for i in range(rows)]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--update-snapshots", action="store_true", default=False)


@pytest.fixture
def snap(request: pytest.FixtureRequest) -> SnapFn:
    update = bool(request.config.getoption("--update-snapshots"))
    module = request.path.stem
    test_name = request.function.__name__

    def _snap(
        node: object, w: int, h: int | None = None, *, name: str | None = None
    ) -> None:
        lines = render(node, w, h)
        key = name or test_name
        path = SNAP_DIR / module / f"{key}.snap"
        content = "\n".join(lines) + "\n" if lines else ""
        if update or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return
        expected = path.read_text()
        assert content == expected

    return _snap
