"""Pixel capture under the mouse cursor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import win32


@dataclass(frozen=True)
class PixelSample:
    x: int
    y: int
    r: int
    g: int
    b: int
    at: datetime

    @property
    def hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    @property
    def rgb(self) -> str:
        return f"({self.r}, {self.g}, {self.b})"

    def summary(self) -> str:
        return f"{self.hex}  ({self.x}, {self.y})  {self.at:%H:%M:%S}"


def capture() -> PixelSample:
    """Read the cursor position and the screen color at that point."""
    x, y = win32.get_cursor_pos()
    r, g, b = win32.get_pixel(x, y)
    return PixelSample(x, y, r, g, b, datetime.now())
