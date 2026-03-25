"""Headless fuzzy picker — pure state, no I/O, no styling."""

from __future__ import annotations

from dataclasses import dataclass

from terminal.text_input import TextInput


def _fuzzy_match(query: str, text: str) -> list[int] | None:
    if not query:
        return []
    indices: list[int] = []
    qi = 0
    q_lower = query.lower()
    t_lower = text.lower()
    for i, ch in enumerate(t_lower):
        if qi < len(q_lower) and ch == q_lower[qi]:
            indices.append(i)
            qi += 1
    return indices if qi == len(q_lower) else None


@dataclass
class Item:
    name: str
    cursor: bool
    selected: bool


@dataclass
class View:
    query: str
    total: int
    filtered: int
    selected: int
    items: list[Item]


class Picker:
    def __init__(
        self,
        choices: list[dict[str, str]],
        *,
        multiselect: bool = False,
        max_height: int = 20,
    ):
        self.choices = choices
        self.multiselect = multiselect
        self.max_height = max_height
        self._qi = TextInput()
        self.cursor = 0
        self.scroll = 0
        self.selected: set[int] = set()
        self._filtered: list[tuple[int, list[int]]] = []
        self._prev_query = ""
        self._filter()

    @property
    def query(self) -> str:
        return self._qi.value

    @query.setter
    def query(self, value: str):
        self._qi.value = value
        self._qi.cursor = len(value)
        self._prev_query = value
        self._filter()

    @property
    def value(self) -> list[str] | str | None:
        if self.multiselect:
            return [self.choices[i]["value"] for i in sorted(self.selected)]
        if self._filtered:
            return self.choices[self._filtered[self.cursor][0]]["value"]
        return None

    _EVENTS: dict[str, str] = {"esc": "cancel", "ctrl-r": "confirm", "enter": "select"}

    def handle_key(self, key: str) -> str | None:
        """Process a key. Returns event name or None.

        Events: "select" (enter), "cancel" (esc), "confirm" (ctrl+r).
        """
        event = self._EVENTS.get(key)
        if event:
            return event
        if key == "up":
            if self.cursor > 0:
                self.cursor -= 1
                self.scroll = min(self.scroll, self.cursor)
        elif key == "down":
            if self.cursor < len(self._filtered) - 1:
                self.cursor += 1
                if self.cursor >= self.scroll + self.max_height:
                    self.scroll = self.cursor - self.max_height + 1
        elif key == "shift-tab" and self.multiselect:
            if self.selected:
                self.selected.clear()
            else:
                self.selected.update(i for i, _ in self._filtered)
        elif key == "tab" and self.multiselect:
            if self._filtered:
                self.selected.symmetric_difference_update({self._filtered[self.cursor][0]})
        elif self._qi.handle_key(key) and self._qi.value != self._prev_query:
            self._prev_query = self._qi.value
            self._filter()
        return None

    def view(self) -> View:
        items: list[Item] = []
        visible_end = min(self.scroll + self.max_height, len(self._filtered))
        for vi in range(self.scroll, visible_end):
            orig_idx, _indices = self._filtered[vi]
            items.append(Item(
                name=self.choices[orig_idx]["name"],
                cursor=vi == self.cursor,
                selected=orig_idx in self.selected,
            ))

        return View(
            query=self._qi.display(),
            total=len(self.choices),
            filtered=len(self._filtered),
            selected=len(self.selected),
            items=items,
        )

    def _filter(self) -> None:
        self._filtered = []
        for i, choice in enumerate(self.choices):
            indices = _fuzzy_match(self._qi.value, choice["name"])
            if indices is not None:
                self._filtered.append((i, indices))
        self.cursor = min(self.cursor, max(0, len(self._filtered) - 1))
        self.scroll = min(self.scroll, max(0, len(self._filtered) - self.max_height))
