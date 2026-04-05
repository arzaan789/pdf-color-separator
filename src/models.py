from dataclasses import dataclass
from enum import Enum, auto


@dataclass(frozen=True)
class Color:
    r: int  # 0-255
    g: int
    b: int

    def __str__(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


class Action(Enum):
    KEEP = auto()
    KEEP_BLACK = auto()
    DELETE = auto()
