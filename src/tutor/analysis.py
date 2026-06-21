"""
Pure-Python deck analysis helpers. No I/O — takes already-fetched Card objects.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from src.scryfall.models import Card


@dataclass
class ManaCurve:
    distribution: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))
    land_count: int = 0

    def average_cmc(self) -> float:
        total_cmc = sum(cmc * len(names) for cmc, names in self.distribution.items())
        total_nonland = sum(len(names) for names in self.distribution.values())
        return round(total_cmc / total_nonland, 2) if total_nonland else 0.0

    def summary(self) -> str:
        lines = [f"  Lands: {self.land_count}"]
        for cmc in sorted(self.distribution):
            cards = self.distribution[cmc]
            label = f"CMC {cmc}" if cmc < 7 else "CMC 7+"
            lines.append(f"  {label}: {len(cards)} ({', '.join(cards[:3])}{'…' if len(cards) > 3 else ''})")
        lines.append(f"  Average CMC (non-land): {self.average_cmc()}")
        return "\n".join(lines)


@dataclass
class DeckCategories:
    ramp: list[str] = field(default_factory=list)
    card_draw: list[str] = field(default_factory=list)
    removal: list[str] = field(default_factory=list)
    counterspells: list[str] = field(default_factory=list)
    board_wipes: list[str] = field(default_factory=list)
    planeswalkers: list[str] = field(default_factory=list)
    creatures: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)

    def summary(self) -> str:
        sections = [
            ("Ramp", self.ramp),
            ("Card Draw", self.card_draw),
            ("Removal", self.removal),
            ("Counterspells", self.counterspells),
            ("Board Wipes", self.board_wipes),
            ("Planeswalkers", self.planeswalkers),
            ("Creatures (other)", self.creatures),
        ]
        lines = []
        for label, cards in sections:
            if cards:
                sample = ", ".join(cards[:4])
                suffix = "…" if len(cards) > 4 else ""
                lines.append(f"  {label} ({len(cards)}): {sample}{suffix}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Keyword sets for heuristic categorization
# ---------------------------------------------------------------------------

_RAMP_NAMES = {
    "sol ring", "arcane signet", "cultivate", "kodama's reach", "farseek",
    "rampant growth", "nature's lore", "three visits", "chromatic lantern",
    "skyshroud claim", "explosive vegetation", "tempt with discovery",
    "mirari's wake", "smothering tithe", "dockside extortionist",
}
_RAMP_TYPE_KEYWORDS = {"mana rock", "mana dork"}
_RAMP_ORACLE_KEYWORDS = {"add {", "add one mana", "search your library for a basic land"}

_DRAW_ORACLE_KEYWORDS = {"draw a card", "draw cards", "draw two", "draw three", "draws a card"}

_REMOVAL_ORACLE_KEYWORDS = {
    "destroy target", "exile target", "return target",
    "deals damage to target", "target creature gets -",
}
_COUNTERSPELL_ORACLE_KEYWORDS = {"counter target spell", "counter that spell", "counter any target"}

_WIPE_ORACLE_KEYWORDS = {
    "destroy all", "exile all", "all creatures get", "each creature gets",
    "-x/-x to each", "deals damage to each",
}


def _oracle(card: Card) -> str:
    return (card.oracle_text or "").lower()

def _type(card: Card) -> str:
    return card.type_line.lower()


def build_mana_curve(entries: list[tuple[int, Card]]) -> ManaCurve:
    """
    Build a mana curve from (quantity, Card) pairs so that
    e.g. 30 Mountains count as 30 lands, not 1.
    """
    curve = ManaCurve()
    for qty, card in entries:
        if "land" in _type(card):
            curve.land_count += qty
        else:
            bucket = min(int(card.cmc), 7)
            curve.distribution[bucket].extend([card.name] * qty)
    return curve


def categorize_cards(cards: list[Card]) -> DeckCategories:
    cats = DeckCategories()
    for card in cards:
        oracle = _oracle(card)
        type_line = _type(card)

        if "land" in type_line:
            continue  # lands handled by mana curve

        placed = False

        if "planeswalker" in type_line:
            cats.planeswalkers.append(card.name)
            placed = True

        if not placed and (
            card.name.lower() in _RAMP_NAMES
            or any(k in oracle for k in _RAMP_ORACLE_KEYWORDS)
            and ("artifact" in type_line or "enchantment" in type_line or "creature" in type_line or "sorcery" in type_line or "instant" in type_line)
        ):
            cats.ramp.append(card.name)
            placed = True

        if not placed and any(k in oracle for k in _WIPE_ORACLE_KEYWORDS):
            cats.board_wipes.append(card.name)
            placed = True

        if not placed and any(k in oracle for k in _COUNTERSPELL_ORACLE_KEYWORDS):
            cats.counterspells.append(card.name)
            placed = True

        if not placed and any(k in oracle for k in _REMOVAL_ORACLE_KEYWORDS):
            cats.removal.append(card.name)
            placed = True

        if not placed and any(k in oracle for k in _DRAW_ORACLE_KEYWORDS):
            cats.card_draw.append(card.name)
            placed = True

        if not placed and "creature" in type_line:
            cats.creatures.append(card.name)
            placed = True

        if not placed:
            cats.other.append(card.name)

    return cats


_WUBRG_ORDER = ["W", "U", "B", "R", "G"]
_COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}


def color_identity_label(color_identity: list[str]) -> str:
    ordered = sorted(color_identity, key=lambda c: _WUBRG_ORDER.index(c) if c in _WUBRG_ORDER else 99)
    return "/".join(_COLOR_NAMES.get(c, c) for c in ordered) or "Colorless"
