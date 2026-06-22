import asyncio
import time
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
        # Lazy: must be created inside a running event loop.
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        await self._throttle()
        for attempt in range(4):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        f"{self._base_url}{path}",
                        params=params or None,
                        headers={"User-Agent": "mtg-edh-tutor/0.1 (github.com/user/mtg-edh-tutor)"},
                    )
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError):
                wait = 2 ** attempt  # 1s, 2s, 4s, 8s
                await asyncio.sleep(wait)
                continue
            if resp.status_code == 404:
                raise CardNotFoundError(f"Not found: {path}")
            if resp.status_code == 429:
                wait = 2 ** attempt
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        raise ScryfallError(f"Scryfall request failed after retries: {path}")

    async def _throttle(self) -> None:
        async with self._get_lock():
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
            except (CardNotFoundError, ScryfallError, httpx.TimeoutException):
                return name, None

        results = await asyncio.gather(*[_fetch(n) for n in names])
        return {name: card for name, card in results if card is not None}
