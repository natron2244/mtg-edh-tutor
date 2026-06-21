from src.scryfall.models import Card, CardLegalities
from src.tutor.analysis import (
    DeckCategories,
    build_mana_curve,
    categorize_cards,
    color_identity_label,
)


def _card(name: str, cmc: float, type_line: str, oracle: str = "", colors: list[str] | None = None) -> Card:
    return Card(
        id="test",
        name=name,
        cmc=cmc,
        type_line=type_line,
        oracle_text=oracle,
        color_identity=colors or [],
        legalities=CardLegalities(commander="legal"),
    )


def test_mana_curve_lands_excluded():
    cards = [
        _card("Command Tower", 0, "Land"),
        _card("Sol Ring", 1, "Artifact", "add {C}{C}"),
        _card("Counterspell", 2, "Instant", "counter target spell"),
    ]
    curve = build_mana_curve(cards)
    assert curve.land_count == 1
    assert 1 in curve.distribution
    assert 2 in curve.distribution
    assert 0 not in curve.distribution  # land not bucketed


def test_mana_curve_average():
    cards = [
        _card("A", 2, "Instant"),
        _card("B", 4, "Sorcery"),
    ]
    curve = build_mana_curve(cards)
    assert curve.average_cmc() == 3.0


def test_categorize_counterspell():
    cards = [_card("Counterspell", 2, "Instant", "counter target spell")]
    cats = categorize_cards(cards)
    assert "Counterspell" in cats.counterspells


def test_categorize_board_wipe():
    cards = [_card("Wrath of God", 4, "Sorcery", "destroy all creatures")]
    cats = categorize_cards(cards)
    assert "Wrath of God" in cats.board_wipes


def test_categorize_ramp():
    cards = [_card("Sol Ring", 1, "Artifact", "{T}: add {C}{C}")]
    cats = categorize_cards(cards)
    assert "Sol Ring" in cats.ramp


def test_categorize_planeswalker():
    cards = [_card("Teferi", 5, "Legendary Planeswalker — Teferi")]
    cats = categorize_cards(cards)
    assert "Teferi" in cats.planeswalkers


def test_categorize_land_skipped():
    cards = [_card("Forest", 0, "Basic Land — Forest")]
    cats = categorize_cards(cards)
    total = (
        len(cats.ramp) + len(cats.card_draw) + len(cats.removal) +
        len(cats.counterspells) + len(cats.board_wipes) +
        len(cats.planeswalkers) + len(cats.creatures) + len(cats.other)
    )
    assert total == 0


def test_color_identity_label():
    assert color_identity_label(["W", "U", "B", "G"]) == "White/Blue/Black/Green"
    assert color_identity_label([]) == "Colorless"
    assert color_identity_label(["G"]) == "Green"
