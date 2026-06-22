"""
Phase 3 unit tests — card cache, structured output parsing, JSON extraction.
No LLM or Scryfall calls.
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.scryfall.models import Card, CardLegalities
from src.tutor.cache import CardCache
from src.tutor.document import DeckDocument, _commander_slug
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


# ------------------------------------------------------------------
# DeckDocument
# ------------------------------------------------------------------

def test_commander_slug():
    assert _commander_slug("Atraxa, Praetors' Voice") == "atraxa_praetors_voice"
    assert _commander_slug("Kumano, Master Yamabushi") == "kumano_master_yamabushi"


def test_deck_document_default_path(tmp_path: Path):
    import os
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        doc = DeckDocument.create("Sol Ring")
        assert doc.path.name == "sol_ring_analysis.md"
    finally:
        os.chdir(old_cwd)


def test_deck_document_apply_initial_report(tmp_path: Path):
    report = DeckReport(
        strategy_summary="Mono-red burn.",
        power_level=6,
        strengths=["Fast", "Consistent"],
        weaknesses=["No blue"],
        suggestions=[Suggestion(cut="Mountain", add="Valakut", reason="Synergy")],
    )
    doc = DeckDocument.create("Kumano", output_path=tmp_path / "test.md")
    doc.apply_initial_report(report)
    assert doc.strategy == "Mono-red burn."
    assert doc.power_level == 6
    assert len(doc.swaps) == 1
    assert doc.swaps[0].cut == "Mountain"


def test_deck_document_merge_deduplicates(tmp_path: Path):
    doc = DeckDocument.create("Kumano", output_path=tmp_path / "test.md")
    s1 = Suggestion(cut="Swamp", add="Island", reason="First")
    s2 = Suggestion(cut="swamp", add="Forest", reason="Dupe")  # same cut, different case
    doc.merge_chat_suggestions([s1], note="turn 1")
    doc.merge_chat_suggestions([s2], note="turn 2")
    assert len(doc.swaps) == 1  # deduped by cut.lower()
    assert len(doc.notes) == 2


def test_deck_document_write_renders_markdown(tmp_path: Path):
    doc = DeckDocument.create("Kumano", output_path=tmp_path / "out.md")
    doc.strategy = "Pinger synergy."
    doc.power_level = 7
    doc.strengths = ["Consistent"]
    doc.weaknesses = ["Slow"]
    doc.swaps = [Suggestion(cut="Mountain", add="Valakut", reason="Wins games")]
    doc.notes = ["Asked about budget options"]
    doc.write()

    text = (tmp_path / "out.md").read_text()
    assert "## Deck Description" in text
    assert "Pinger synergy." in text
    assert "## Strengths" in text
    assert "## Weaknesses" in text
    assert "## Cuts & Adds" in text
    assert "Mountain" in text
    assert "Valakut" in text
    assert "## Notes" in text
    assert "Asked about budget options" in text


# ------------------------------------------------------------------
# extract_chat_suggestions (mocked LLM)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_chat_suggestions_parses():
    from src.llm.base import LLMResponse, Message, Role
    from src.tutor.structured import extract_chat_suggestions

    llm = MagicMock()
    llm.chat = AsyncMock(return_value=LLMResponse(
        content='{"suggestions": [{"cut": "Forest", "add": "Taiga", "reason": "Dual land"}]}',
        tool_calls=[],
        stop_reason="end_turn",
    ))
    history = [Message(role=Role.USER, content="What cuts?")]
    suggestions = await extract_chat_suggestions(llm, history, "system")
    assert len(suggestions) == 1
    assert suggestions[0].cut == "Forest"
    assert suggestions[0].add == "Taiga"


@pytest.mark.asyncio
async def test_extract_chat_suggestions_empty_on_parse_fail():
    from src.llm.base import LLMResponse, Message, Role
    from src.tutor.structured import extract_chat_suggestions

    llm = MagicMock()
    llm.chat = AsyncMock(return_value=LLMResponse(
        content="not json at all",
        tool_calls=[],
        stop_reason="end_turn",
    ))
    history = [Message(role=Role.USER, content="Hmm?")]
    suggestions = await extract_chat_suggestions(llm, history, "system")
    assert suggestions == []
