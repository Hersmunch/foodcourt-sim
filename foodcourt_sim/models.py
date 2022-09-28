from __future__ import annotations

import functools
from dataclasses import dataclass
from enum import Enum, unique
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from .entities import Entity


__all__ = [
    "Direction",
    "RelativeDirection",
    "Position",
    "MoveEntity",
]


@unique
class Direction(Enum):
    RIGHT = 0
    UP = 1
    LEFT = 2
    DOWN = 3

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    def right(self) -> Direction:
        return Direction((self.value - 1) % 4)

    def left(self) -> Direction:
        return Direction((self.value + 1) % 4)

    def back(self) -> Direction:
        return Direction((self.value + 2) % 4)

    def relative_to(self, base: Direction) -> RelativeDirection:
        return RelativeDirection((self.value - base.value) % 4)


@unique
class RelativeDirection(Enum):
    FRONT = 0
    RIGHT = 1
    BACK = 2
    LEFT = 3

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class Position(NamedTuple):
    # origin is at lower left corner
    column: int
    row: int

    def __repr__(self) -> str:
        return f"({self.column}, {self.row})"

    def copy(self) -> Position:
        return Position(self.column, self.row)

    def shift_by(self, direction: Direction) -> Position:
        col, row = self
        if direction is Direction.RIGHT:
            col += 1
        elif direction is Direction.LEFT:
            col -= 1
        elif direction is Direction.UP:
            row += 1
        elif direction is Direction.DOWN:
            row -= 1
        return Position(col, row)


@functools.total_ordering  # optimization note: this adds some overhead (see the docs)
@dataclass(frozen=True, eq=False)
class MoveEntity:
    """Represents a pending entity movement on the factory floor."""

    entity: Entity
    direction: Direction
    force: bool = True

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MoveEntity):
            return NotImplemented
        return (id(self.entity), self.direction, self.force) == (
            id(other.entity),
            other.direction,
            other.force,
        )

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, MoveEntity):
            return NotImplemented
        return (id(self.entity), self.direction.value, self.force) < (
            id(other.entity),
            other.direction.value,
            other.force,
        )

    @functools.cached_property
    def source(self) -> Position:
        return self.entity.position

    @functools.cached_property
    def dest(self) -> Position:
        return self.entity.position.shift_by(self.direction)
