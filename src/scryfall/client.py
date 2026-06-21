import asyncio
from typing import Any

import httpx

from src.config import settings
from .models import Card


class ScryfallError(Exception):
    pass


class CardNotFoundError(ScryfallError):
    pass


class ScryfallClient:
    def __init__(
        self,
        base_url: str | None = None,
        rate_limit_delay: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.scryfall_base_url).rstrip("/")
        self._delay = rate_limit_delay if rate_limit_delay is not None else settings.scryfall_rate_limit_delay
        self._last_request: float = 0.0

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        await self._throttle()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}{path}",
                params=params or None,
                headers={"User-Agent": "mtg-edh-tutor/0.1 (github.com/user/mtg-edh-tutor)"},
            )
            if resp.status_code == 404:
                raise CardNotFoundError(f"Not found: {path}")
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]

    async def _throttle(self) -> None:
        import time
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last_request = time.monotonic()

    async def get_card_by_name(self, name: str, exact: bool = True) -> Card:
        """Fetch a single card by name. Uses /cards/named endpoint."""
        params = {"exact": name} if exact else {"fuzzy": name}
        data = await self._get("/cards/named", **params)
        return Card.model_validate(data)

    async def get_card_by_id(self, scryfall_id: str) -> Card:
        data = await self._get(f"/cards/{scryfall_id}")
        return Card.model_validate(data)

    async def search_cards(self, query: str, limit: int = 20) -> list[Card]:
        """Full-text Scryfall search. Returns up to `limit` results."""
        try:
            data = await self._get("/cards/search", q=query)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise
        results = []
        for card_data in data.get("data", [])[:limit]:
            try:
                results.append(Card.model_validate(card_data))
            except Exception:
                continue
        return results

    async def get_cards_by_names(self, names: list[str]) -> dict[str, Card]:
        """Fetch multiple cards concurrently. Returns {name: Card} mapping."""
        async def _fetch(name: str) -> tuple[str, Card | None]:
            try:
                card = await self.get_card_by_name(name, exact=False)
                return name, card
            except (CardNotFoundError, ScryfallError):
                return name, None

        results = await asyncio.gather(*[_fetch(n) for n in names])
        return {name: card for name, card in results if card is not None}
