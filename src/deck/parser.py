"""
Parse standard MTG decklist text formats into Deck objects.

Supported formats:
  - MTGO / Moxfield:   "1 Sol Ring" or "1x Sol Ring"
  - Section headers:   "Commander", "Deck", "Sideboard" (case-insensitive)
  - Inline commander:  "*CMDR* 1 Atraxa, Praetors' Voice"
  - Comments:          lines starting with "//" or "#" are ignored
"""
import re

from .models import CardEntry, Deck, Zone

# Matches: optional "*CMDR*", quantity ("1" or "1x"), then card name
_CARD_LINE = re.compile(
    r"^(?P<cmdr>\*CMDR\*\s+)?"
    r"(?P<qty>\d+)x?\s+"
    r"(?P<name>.+?)(?:\s+\([A-Z0-9]+\)\s+\d+)?$",
    re.IGNORECASE,
)

_SECTION_HEADERS = {
    "commander": Zone.COMMANDER,
    "commanders": Zone.COMMANDER,
    "deck": Zone.MAINBOARD,
    "mainboard": Zone.MAINBOARD,
    "main": Zone.MAINBOARD,
    "sideboard": Zone.SIDEBOARD,
    "side": Zone.SIDEBOARD,
}


def parse_decklist(text: str, commander_override: str | None = None) -> Deck:
    """
    Parse a plain-text decklist into a Deck.

    Args:
        text: The raw decklist string.
        commander_override: If set, treat this card name as the commander
                            regardless of zone markers in the text.
    """
    deck = Deck()
    current_zone = Zone.MAINBOARD

    for raw_line in text.splitlines():
        line = raw_line.strip()

        # Skip blank lines and comments
        if not line or line.startswith("//") or line.startswith("#"):
            continue

        # Section header?
        lower = line.lower().rstrip(":")
        if lower in _SECTION_HEADERS:
            current_zone = _SECTION_HEADERS[lower]
            continue

        m = _CARD_LINE.match(line)
        if not m:
            continue

        name = m.group("name").strip()
        qty = int(m.group("qty"))
        is_cmdr_marker = bool(m.group("cmdr"))

        zone = Zone.COMMANDER if is_cmdr_marker else current_zone
        deck.entries.append(CardEntry(name=name, quantity=qty, zone=zone))

    if commander_override:
        deck.commander_name = commander_override
        # Mark the matching entry as commander zone
        for entry in deck.entries:
            if entry.name.lower() == commander_override.lower():
                entry.zone = Zone.COMMANDER
                break

    return deck


def parse_decklist_file(path: str, commander_override: str | None = None) -> Deck:
    with open(path, encoding="utf-8") as f:
        return parse_decklist(f.read(), commander_override=commander_override)
