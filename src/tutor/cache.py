"""
Card cache — in-memory dict backed by a JSON file on disk.

Acts as the RAG retrieval layer: cards fetched from Scryfall during deck
loading are instantly available when the LLM later calls lookup_card, and
persist across CLI sessions so the same card is never fetched twice.
"""
import asyncio
import json
from pathlib import Path

from src.scryfall import CardNotFoundError, ScryfallClient
from src.scryfall.models import Card

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "edh-tutor"


class CardCache:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self._dir = cache_dir or _DEFAULT_CACHE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "cards.json"
        self._scryfall = ScryfallClient()
        # In-memory index: normalized name → Card
        self._store: dict[str, Card] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, name: str) -> Card | None:
        """Return a cached card or None if not in cache."""
        return self._store.get(self._key(name))

    async def fetch(self, name: str) -> Card:
        """Return card from cache, or fetch from Scryfall and cache it."""
        key = self._key(name)
        if key in self._store:
            return self._store[key]
        card = await self._scryfall.get_card_by_name(name, exact=False)
        self._store[key] = card
        self._save(card)
        return card

    async def prefetch(self, names: list[str]) -> dict[str, Card]:
        """
        Fetch a batch of cards concurrently, skipping those already cached.
        Returns {original_name: Card} for every card successfully retrieved.
        """
        missing = [n for n in names if self._key(n) not in self._store]

        if missing:
            fetched = await self._scryfall.get_cards_by_names(missing)
            for orig_name, card in fetched.items():
                key = self._key(orig_name)
                self._store[key] = card
            self._flush()

        result: dict[str, Card] = {}
        for name in names:
            card = self._store.get(self._key(name))
            if card:
                result[name] = card
        return result

    def get_sync(self, name: str) -> Card | None:
        return self._store.get(self._key(name))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _key(self, name: str) -> str:
        return name.lower().strip()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw: dict[str, object] = json.loads(self._path.read_text(encoding="utf-8"))
            for name, data in raw.items():
                try:
                    self._store[name] = Card.model_validate(data)
                except Exception:
                    continue
        except Exception:
            pass  # corrupt cache — start fresh

    def _save(self, card: Card) -> None:
        """Append a single card to the on-disk cache."""
        self._flush()

    def _flush(self) -> None:
        """Write the full in-memory store to disk."""
        try:
            payload = {k: v.model_dump() for k, v in self._store.items()}
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except Exception:
            pass  # non-fatal — cache is best-effort
