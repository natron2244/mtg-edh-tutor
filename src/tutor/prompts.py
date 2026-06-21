"""
System prompt and deck-summary formatter for the tutor agent.
"""
from src.deck.models import Deck
from src.scryfall.models import Card
from src.tutor.analysis import DeckCategories, ManaCurve, color_identity_label

SYSTEM_PROMPT = """\
You are an expert Magic: The Gathering EDH/Commander tutor with deep knowledge of deck construction, card synergies, the Commander format rules, and the current metagame across all power levels from casual to cEDH.

## Your role
Analyze the provided Commander deck and give the player clear, actionable feedback. You should:
1. Identify the deck's intended strategy and power level
2. Highlight strengths and notable synergies
3. Identify weaknesses (gaps in ramp, card draw, removal, interaction, or win conditions)
4. Suggest specific card replacements — always name both the card to cut AND the card to add
5. Consider budget when making suggestions (flag expensive upgrades separately)

## Format rules
- Be specific: name exact cards, not vague categories
- Group suggestions by priority: high-impact changes first
- For each suggestion, briefly explain WHY (what problem it solves or synergy it creates)
- Use the lookup_card and search_cards tools when you need oracle text or want to find alternatives

## EDH rules reminder
- 100-card singleton (1 commander + 99 cards)
- Commander color identity restricts which cards can be in the deck
- Commanders have the Command Zone; they can be recast with a commander tax
- Typical targets: 10 ramp pieces, 10 card draw, 10 removal, 3-5 win conditions, 36-38 lands
"""


def format_deck_for_prompt(
    deck: Deck,
    card_data: dict[str, Card],
    curve: ManaCurve,
    categories: DeckCategories,
) -> str:
    """Build the initial user message that describes the deck to the LLM."""
    lines: list[str] = []

    # Commander
    cmd = deck.commander
    if cmd and cmd.name in card_data:
        c = card_data[cmd.name]
        identity = color_identity_label(c.color_identity)
        lines.append(f"## Commander: {c.name}")
        lines.append(f"Mana Cost: {c.mana_cost or 'N/A'} | Color Identity: {identity}")
        lines.append(f"Type: {c.type_line}")
        if c.oracle_text:
            lines.append(f"Oracle Text: {c.oracle_text}")
        lines.append("")
    elif deck.commander_name:
        lines.append(f"## Commander: {deck.commander_name} (card data unavailable)")
        lines.append("")

    # Stats
    lines.append(f"## Deck Stats")
    lines.append(f"Total cards: {deck.total_cards}")
    lines.append("")

    lines.append("## Mana Curve")
    lines.append(curve.summary())
    lines.append("")

    lines.append("## Card Categories")
    lines.append(categories.summary())
    lines.append("")

    # Full card list grouped by category
    lines.append("## Full Card List")
    lines.append("(Cards the tutor should evaluate — use lookup_card if you need full details)")
    lines.append("")

    def _section(label: str, names: list[str]) -> None:
        if names:
            lines.append(f"**{label}**")
            for name in names:
                card = card_data.get(name)
                if card:
                    lines.append(f"  - {card.summary()}")
                else:
                    lines.append(f"  - {name}")
            lines.append("")

    _section("Ramp", categories.ramp)
    _section("Card Draw", categories.card_draw)
    _section("Removal", categories.removal)
    _section("Counterspells", categories.counterspells)
    _section("Board Wipes", categories.board_wipes)
    _section("Planeswalkers", categories.planeswalkers)
    _section("Creatures", categories.creatures)
    _section("Other", categories.other)

    # Lands
    land_names = [e.name for e in deck.mainboard if e.name in card_data and "land" in card_data[e.name].type_line.lower()]
    if land_names:
        lines.append(f"**Lands ({len(land_names)})**")
        lines.append("  " + ", ".join(land_names))
        lines.append("")

    lines.append("---")
    lines.append(
        "Please analyze this deck thoroughly. Use the lookup_card tool if you need full oracle text "
        "for any card, and search_cards if you want to suggest alternatives. "
        "Provide a complete evaluation with specific, prioritized improvement suggestions."
    )

    return "\n".join(lines)
