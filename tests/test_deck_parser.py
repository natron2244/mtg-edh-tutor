from src.deck import Zone, parse_decklist, parse_decklist_file


SIMPLE_DECK = """\
Commander
1 Atraxa, Praetors' Voice

Deck
1 Sol Ring
1 Command Tower
1 Counterspell
"""


def test_parse_commander_zone():
    deck = parse_decklist(SIMPLE_DECK)
    assert deck.commander is not None
    assert deck.commander.name == "Atraxa, Praetors' Voice"
    assert deck.commander.zone == Zone.COMMANDER


def test_parse_mainboard_count():
    deck = parse_decklist(SIMPLE_DECK)
    assert len(deck.mainboard) == 3


def test_total_cards():
    deck = parse_decklist(SIMPLE_DECK)
    assert deck.total_cards == 4  # 1 commander + 3 mainboard


def test_quantity_x_format():
    deck = parse_decklist("Deck\n4x Lightning Bolt\n")
    assert deck.mainboard[0].quantity == 4
    assert deck.mainboard[0].name == "Lightning Bolt"


def test_comment_lines_ignored():
    deck = parse_decklist("// This is a comment\n# Also a comment\nDeck\n1 Sol Ring\n")
    assert len(deck.mainboard) == 1


def test_cmdr_inline_marker():
    deck = parse_decklist("*CMDR* 1 Atraxa, Praetors' Voice\n1 Sol Ring\n")
    assert deck.commander is not None
    assert deck.commander.name == "Atraxa, Praetors' Voice"


def test_commander_override():
    text = "1 Sol Ring\n1 Atraxa, Praetors' Voice\n"
    deck = parse_decklist(text, commander_override="Atraxa, Praetors' Voice")
    assert deck.commander is not None
    assert deck.commander.zone == Zone.COMMANDER


def test_parse_from_file():
    deck = parse_decklist_file("tests/fixtures/sample_deck.txt")
    assert deck.commander is not None
    assert deck.commander.name == "Atraxa, Praetors' Voice"
    assert deck.total_cards > 90  # EDH decks are 100 cards
