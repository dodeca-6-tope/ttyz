"""Keyed protocol — items that can be identified by a stable key."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Protocol, runtime_checkable


@runtime_checkable
class Keyed(Protocol):
    @property
    def key(self) -> Hashable: ...
