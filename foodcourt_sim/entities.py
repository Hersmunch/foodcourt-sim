from __future__ import annotations

import dataclasses
import functools
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from .enums import EntityId, PaintColor, ToppingId
from .models import Position

if TYPE_CHECKING:
    from .operations import Operation
    from .simulator import State


_TRAY_WHITELIST = set(EntityId) - {
    EntityId.LID,  # soda trench, belly's
    EntityId.ROAST,  # sweet heat bbq
    EntityId.RIBS,  # sweet heat bbq
    EntityId.ICE,  # the walrus
    EntityId.PAPER,  # cafe triste
    EntityId.CIGARETTE_4X,  # cafe triste
    EntityId.CIGARETTE_2X,  # cafe triste
    EntityId.POTATO,  # belly's
    EntityId.ONION,  # belly's
    EntityId.NORI,  # sushi yeah!
    EntityId.RICE,  # sushi yeah!
    EntityId.TUNA,  # sushi yeah!
    EntityId.SALMON,  # sushi yeah!
    EntityId.TUNA_MAKI_4X,  # sushi yeah!
    EntityId.TUNA_MAKI_2X,  # sushi yeah!
    EntityId.TUNA_MAKI,  # sushi yeah!
    EntityId.SALMON_MAKI_4X,  # sushi yeah!
    EntityId.SALMON_MAKI_2X,  # sushi yeah!
    EntityId.SALMON_MAKI,  # sushi yeah!
}

_BURGER_PARTS = {
    EntityId.BUN,
    EntityId.BUN_BOTTOM,
    EntityId.BUN_TOP,
    EntityId.MEAT,
    EntityId.CHEESE,
    EntityId.PICKLE,
    EntityId.TOMATO,
}
_STACK_WHITELIST = {
    EntityId.TRAY: _TRAY_WHITELIST,
    EntityId.MULTITRAY: _TRAY_WHITELIST,
    EntityId.CUP: {EntityId.LID, EntityId.ICE, EntityId.POTATO, EntityId.ONION},
    **{part: _BURGER_PARTS for part in _BURGER_PARTS},
    EntityId.NORI: {EntityId.RICE},
    EntityId.RICE: {EntityId.TUNA, EntityId.SALMON},
    EntityId.BOWL: {EntityId.RICE},
    EntityId.PLATE: {EntityId.TUNA_MAKI, EntityId.SALMON_MAKI, EntityId.RICE},
}


@functools.total_ordering  # optimization note: this adds some overhead (see the docs)
@dataclass(eq=False, repr=False)
class Entity:
    """Something that rides on conveyors."""

    id: EntityId
    # all the operations that were performed on this entity, in order
    operations: list[Operation] = field(default_factory=list)
    # the entity that is stacked on this entity
    stack: Optional[Entity] = None

    position: Position = Position(-1, -1)

    def __post_init__(self) -> None:
        # TODO: this is just to make sure I implement things right, and should be removed once testing is done
        if self.id in (
            EntityId.MULTITRAY,
            EntityId.CUP,
            EntityId.WING_PLACEHOLDER,
            EntityId.BUN_BOTTOM,
            EntityId.NORI,
            EntityId.PLATE,
        ):
            assert self.__class__ is not Entity, "code mistake: must use subclasses"

    def __repr__(self) -> str:
        include_id = self.__class__ is Entity
        field_descs = [
            f"{f.name}={value!r}"
            for f in dataclasses.fields(self)
            for value in [getattr(self, f.name)]
            if (value or value == 0)
            and value != Position(-1, -1)
            and (include_id or f.name != "id")
        ]
        return f"{self.__class__.__name__}({', '.join(field_descs)})"

    def _compare_key(self) -> tuple[Any, ...]:
        return (self.id, self.operations, self.stack)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self._compare_key() == other._compare_key()

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self._compare_key() < other._compare_key()

    def add_to_stack(self, state: State, other: Entity, error: Exception) -> None:
        # default behavior:
        if other.id not in _STACK_WHITELIST.get(self.id, set()):
            raise error
        if self.stack is None:
            state.remove_entity(other)
            self.stack = other
        else:
            # try to stack on top of existing stack
            self.stack.add_to_stack(state, other, error)


@dataclass(eq=False, repr=False)
class MultiStackEntity(Entity):
    stack: Optional[Entity] = field(init=False, default=None)
    # the entities that are stacked on this entity
    multistack: list[Entity] = field(default_factory=list)

    def _compare_key(self) -> tuple[Any, ...]:
        return (*super()._compare_key(), sorted(self.multistack))

    def add_to_stack(self, state: State, other: Entity, error: Exception) -> None:
        if other.id not in _STACK_WHITELIST[self.id]:
            raise error
        state.remove_entity(other)
        self.multistack.append(other)


@dataclass(eq=False, repr=False)
class Multitray(MultiStackEntity):
    id: EntityId = EntityId.MULTITRAY


@dataclass(eq=False, repr=False)
class ChaatDough(Entity):
    """Dough for Mumbai Chaat."""

    id: EntityId = EntityId.DOUGH

    sauces: set[ToppingId] = field(default_factory=set)

    def _compare_key(self) -> tuple[Any, ...]:
        return (*super()._compare_key(), self.sauces)

    def add_sauce(self, sauce: ToppingId, error: Exception) -> None:
        assert sauce in {ToppingId.TOMATO, ToppingId.MINT, ToppingId.YOGURT}
        if sauce in self.sauces:
            raise error
        self.sauces.add(sauce)


@dataclass(eq=False, repr=False)
class Cup(Entity):
    """Cup that can contain unordered fluids."""

    id: EntityId = EntityId.CUP
    contents: Counter[ToppingId] = field(default_factory=Counter)
    capacity: int = 0

    # def __post_init__(self) -> None:
    #     super().__post_init__()
    #     assert self.capacity != 0

    def _compare_key(self) -> tuple[Any, ...]:
        # use +contents to discard negative and zero counts
        return (*super()._compare_key(), +self.contents)

    def add_fluid(self, fluid: ToppingId, error: Exception) -> None:
        if sum(self.contents.values()) >= self.capacity:
            raise error
        self.contents[fluid] += 1

    def remove_fluid(self, fluid: ToppingId) -> None:
        assert fluid in +self.contents
        self.contents[fluid] -= 1
        if self.contents[fluid] == 0:
            del self.contents[fluid]


@dataclass(eq=False, repr=False)
class PaintableCup(Cup):
    """Paintable cup for Soda Trench."""

    id: EntityId = EntityId.CUP
    # cup paint colors, from top to bottom
    colors: list[PaintColor] = field(default_factory=lambda: [PaintColor.WHITE] * 3)

    def _compare_key(self) -> tuple[Any, ...]:
        return (*super()._compare_key(), self.colors)


@dataclass(eq=False, repr=False)
class WingPlaceholder(Entity):
    """Placeholder entity for Da Wings order checking."""

    id: EntityId = EntityId.WING_PLACEHOLDER

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        # return an object that compares equal to E.CHICKEN_CUTLET and E.CHICKEN_LEG
        if other.id in (EntityId.CHICKEN_CUTLET, EntityId.CHICKEN_LEG):
            return self._compare_key()[1:] == other._compare_key()[1:]
        return False

    # __lt__() can be left as-is, since WING_PLACEHOLDER comes right after
    # CHICKEN_CUTLET and CHICKEN_LEG, and this should only be used in the level
    # definition anyway.


@dataclass(eq=False, repr=False)
class Burger(MultiStackEntity):
    """Burger for Breakside Grill and Belly's."""

    id: EntityId = EntityId.BUN_BOTTOM

    def _compare_key(self) -> tuple[Any, ...]:
        # stack order matters for this entity
        return (*super()._compare_key(), self.multistack)


@dataclass(eq=False, repr=False)
class PizzaDough(Entity):
    """Pizza dough for Chaz Cheddar."""

    id: EntityId = EntityId.DOUGH
    left_toppings: set[ToppingId] = field(default_factory=set)
    right_toppings: set[ToppingId] = field(default_factory=set)

    def _compare_key(self) -> tuple[Any, ...]:
        return (
            *super()._compare_key(),
            self.left_toppings,
            self.right_toppings,
        )


@dataclass(eq=False, repr=False)
class DoubleStackEntity(Entity):
    """Entity that has two independent stacks."""

    stack: Optional[Entity] = field(init=False, default=None)
    left_stack: Optional[Entity] = None
    right_stack: Optional[Entity] = None

    def _compare_key(self) -> tuple[Any, ...]:
        stacks = sorted(
            [self.left_stack, self.right_stack], key=lambda x: (x is not None, x)
        )
        return (
            *super()._compare_key()[:-1],
            *stacks,
        )

    def add_to_stack(self, state: State, other: Entity, error: Exception) -> None:
        if other.id not in _STACK_WHITELIST[self.id]:
            raise error


@dataclass(eq=False, repr=False)
class Nori(DoubleStackEntity):
    """Nori sheet for Sushi Yeah!"""

    id: EntityId = EntityId.NORI


@dataclass(eq=False, repr=False)
class SushiPlate(DoubleStackEntity, MultiStackEntity):
    """Plate for Sushi Yeah!"""

    id: EntityId = EntityId.PLATE

    def add_to_stack(self, state: State, other: Entity, error: Exception) -> None:
        if other.id not in _STACK_WHITELIST[self.id]:
            raise error
        if other.id is EntityId.RICE:
            DoubleStackEntity.add_to_stack(self, state, other, error)
        else:
            MultiStackEntity.add_to_stack(self, state, other, error)


@dataclass(eq=False, repr=False)
class SushiBowl(DoubleStackEntity):
    """Bowl for Sushi Yeah!"""

    id: EntityId = EntityId.BOWL