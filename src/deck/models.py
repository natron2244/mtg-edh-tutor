from dataclasses import dataclass, field
from enum import Enum


class Zone(str, Enum):
    MAINBOARD = "mainboard"
    COMMANDER = "commander"
    SIDEBOARD = "sideboard"  # sometimes used for companion/wishboard


@dataclass
class CardEntry:
    name: str
    quantity: int
    zone: Zone = Zone.MAINBOARD


@dataclass
class Deck:
    entries: list[CardEntry] = field(default_factory=list)
    commander_name: str | None = None  # explicit override

    @property
    def commander(self) -> CardEntry | None:
        for e in self.entries:
            if e.zone == Zone.COMMANDER:
                return e
        return None

    @property
    def mainboard(self) -> list[CardEntry]:
        return [e for e in self.entries if e.zone == Zone.MAINBOARD]

    @property
    def all_card_names(self) -> list[str]:
        return [e.name for e in self.entries]

    @property
    def total_cards(self) -> int:
        return sum(e.quantity for e in self.entries)

    def __repr__(self) -> str:
        cmd = self.commander
        cmd_str = f" ({cmd.name})" if cmd else ""
        return f"Deck{cmd_str}: {self.total_cards} cards"
