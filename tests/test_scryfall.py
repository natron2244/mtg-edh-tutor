"""
Scryfall client tests — hits real API. Mark with pytest.mark.integration to skip in offline CI.
"""
import pytest
from src.scryfall import CardNotFoundError, ScryfallClient


@pytest.fixture
def client() -> ScryfallClient:
    return ScryfallClient(rate_limit_delay=0.05)


@pytest.mark.asyncio
async def test_get_card_by_name(client: ScryfallClient):
    card = await client.get_card_by_name("Sol Ring")
    assert card.name == "Sol Ring"
    assert card.is_commander_legal


@pytest.mark.asyncio
async def test_get_card_fuzzy(client: ScryfallClient):
    card = await client.get_card_by_name("Atraxa Praetors Voice", exact=False)
    assert "Atraxa" in card.name


@pytest.mark.asyncio
async def test_card_not_found(client: ScryfallClient):
    with pytest.raises(CardNotFoundError):
        await client.get_card_by_name("zzzzz_not_a_real_card_12345", exact=True)


@pytest.mark.asyncio
async def test_search_cards(client: ScryfallClient):
    results = await client.search_cards("t:artifact t:equipment cmc=1", limit=5)
    assert len(results) > 0
    assert all(r.cmc == 1 for r in results)


@pytest.mark.asyncio
async def test_get_cards_by_names(client: ScryfallClient):
    names = ["Sol Ring", "Command Tower", "Arcane Signet"]
    found = await client.get_cards_by_names(names)
    assert len(found) == 3
    assert "Sol Ring" in found


@pytest.mark.asyncio
async def test_card_summary(client: ScryfallClient):
    card = await client.get_card_by_name("Sol Ring")
    summary = card.summary()
    assert "Sol Ring" in summary
