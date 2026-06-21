"""
Phase 3 unit tests — card cache, structured output parsing, JSON extraction.
No LLM or Scryfall calls.
"""
import json
from pathlib import Path

import pytest

from src.scryfall.models import Card, CardLegalities
from src.tutor.cache import CardCache
from src.tutor.structured import DeckReport, Suggestion, _extract_json


# ------------------------------------------------------------------
# Card cache
# ------------------------------------------------------------------

def _sample_card(name: str = "Sol Ring") -> Card:
    return Card(
        id="abc",
        name=name,
        cmc=1.0,
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
        legalities=CardLegalities(commander="legal"),
    )


@pytest.mark.asyncio
async def test_cache_stores_and_retrieves(tmp_path: Path):
    cache = CardCache(cache_dir=tmp_path)
    card = _sample_card()
    # Manually populate store
    cache._store["sol ring"] = card
    result = await cache.get("Sol Ring")
    assert result is not None
    assert result.name == "Sol Ring"


@pytest.mark.asyncio
async def test_cache_miss_returns_none(tmp_path: Path):
    cache = CardCache(cache_dir=tmp_path)
    result = await cache.get("Nonexistent Card XYZ")
    assert result is None


def test_cache_persists_to_disk(tmp_path: Path):
    cache = CardCache(cache_dir=tmp_path)
    card = _sample_card("Command Tower")
    cache._store["command tower"] = card
    cache._flush()

    cache2 = CardCache(cache_dir=tmp_path)
    assert "command tower" in cache2._store
    assert cache2._store["command tower"].name == "Command Tower"


def test_cache_hit_count():
    from src.tutor.agent import _cache_hit_count
    from unittest.mock import MagicMock
    cache = MagicMock()
    cache.get_sync = lambda n: _sample_card() if n.lower() == "sol ring" else None
    count = _cache_hit_count(cache, ["Sol Ring", "Counterspell"])
    assert count == 1


# ------------------------------------------------------------------
# JSON extraction
# ------------------------------------------------------------------

def test_extract_json_plain():
    text = '{"foo": 1, "bar": "baz"}'
    result = _extract_json(text)
    assert json.loads(result) == {"foo": 1, "bar": "baz"}


def test_extract_json_strips_fences():
    text = "```json\n{\"key\": \"value\"}\n```"
    result = _extract_json(text)
    assert json.loads(result) == {"key": "value"}


def test_extract_json_with_prose():
    text = "Here is the JSON:\n{\"answer\": 42}\nEnd."
    result = _extract_json(text)
    assert json.loads(result) == {"answer": 42}


# ------------------------------------------------------------------
# DeckReport model
# ------------------------------------------------------------------

def test_deck_report_validates():
    data = {
        "strategy_summary": "Proliferate and win with counters.",
        "power_level": 7,
        "strengths": ["Strong ramp", "Good interaction"],
        "weaknesses": ["Weak land base"],
        "suggestions": [
            {"cut": "Swamp", "add": "Watery Grave", "reason": "Better fixing"}
        ],
        "budget_notes": None,
    }
    report = DeckReport.model_validate(data)
    assert report.power_level == 7
    assert len(report.suggestions) == 1
    assert report.suggestions[0].cut == "Swamp"


def test_deck_report_rejects_bad_power_level():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DeckReport(
            strategy_summary="x",
            power_level=11,  # out of range
            strengths=[],
            weaknesses=[],
            suggestions=[],
        )
