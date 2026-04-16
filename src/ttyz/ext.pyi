class Buffer:
    width: int
    height: int
    def __init__(self, width: int, height: int) -> None: ...
    def dump(self) -> str: ...
    def diff(self, prev: Buffer) -> str: ...

class TextRender:
    visible_w: int
    def __init__(
        self,
        value: object,
        truncation: str | None,
        pl: int,
        pr: int,
        wrap: bool,
    ) -> None: ...
    def __call__(self, w: int, h: int | None = None) -> list[str]: ...

def render_to_buffer(node: object, buffer: Buffer, h: int = ...) -> int: ...
