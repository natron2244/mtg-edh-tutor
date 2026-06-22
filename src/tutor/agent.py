"""
TutorSession — stateful agentic conversation that evaluates an EDH deck.

Phase 3 patterns applied:
  - RAG: CardCache pre-populates from Scryfall, tool calls hit cache first
  - Parallel analysis: Scryfall prefetch runs concurrently (asyncio.gather)
  - Structured output: second LLM call extracts a DeckReport from prose analysis
  - Multi-turn: session holds full conversation history; chat() adds new turns
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from src.deck.models import Deck
from src.llm import get_client
from src.llm.base import LLMClient, Message, Role
from src.scryfall import ScryfallClient
from src.tutor.analysis import build_mana_curve, categorize_cards
from src.tutor.cache import CardCache
from src.tutor.prompts import SYSTEM_PROMPT, format_deck_for_prompt
from src.tutor.document import DeckDocument
from src.tutor.structured import DeckReport, extract_chat_suggestions, extract_structured_report
from src.tutor.tools import ALL_TOOLS, execute_tool

MAX_TOOL_ROUNDS = 10
Progress = Callable[[str], None]


@dataclass
class TutorSession:
    """
    Holds the full conversation state for a deck analysis session.
    Create via TutorSession.start() — do not instantiate directly.
    """
    deck: Deck
    llm: LLMClient
    cache: CardCache
    history: list[Message] = field(default_factory=list)
    report: DeckReport | None = None
    document: DeckDocument | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    async def start(
        cls,
        deck: Deck,
        progress: Progress | None = None,
        cache_dir=None,
        output_path=None,
    ) -> tuple["TutorSession", str, DeckReport | None]:
        """
        Bootstrap a session: prefetch cards, run initial analysis, extract
        structured report. Returns (session, prose_analysis, report).
        """
        def _log(msg: str) -> None:
            if progress:
                progress(msg)

        cache = CardCache(cache_dir=cache_dir)
        llm = get_client()

        # ------------------------------------------------------------------
        # 1. Parallel card prefetch (RAG population)
        #    asyncio.gather runs all Scryfall fetches concurrently through
        #    the rate-limited, cached client — demonstrating the parallelization
        #    pattern from the course.
        # ------------------------------------------------------------------
        all_names = list(dict.fromkeys(deck.all_card_names))
        _log(f"Fetching {len(all_names)} cards from Scryfall (cached: {_cache_hit_count(cache, all_names)})…")
        card_data = await cache.prefetch(all_names)
        _log(f"Card data ready ({len(card_data)}/{len(all_names)} retrieved).")

        # ------------------------------------------------------------------
        # 2. Pure-Python analysis — build quantity-aware pairs so that
        #    "30 Mountain" counts as 30 lands, not 1.
        # ------------------------------------------------------------------
        qty_map = {e.name: e.quantity for e in deck.entries}
        qty_card_pairs = [
            (qty_map.get(name, 1), card) for name, card in card_data.items()
        ]
        fetched_cards = list(card_data.values())
        curve = build_mana_curve(qty_card_pairs)
        categories = categorize_cards(fetched_cards)

        # ------------------------------------------------------------------
        # 3. Build initial prompt and run agentic loop
        # ------------------------------------------------------------------
        deck_summary = format_deck_for_prompt(deck, card_data, curve, categories)
        session = cls(deck=deck, llm=llm, cache=cache)
        session.history.append(Message(role=Role.USER, content=deck_summary))

        _log("Running AI analysis…")
        prose = await session._run_agentic_loop(progress=_log)

        # ------------------------------------------------------------------
        # 4. Structured output extraction (second LLM call)
        # ------------------------------------------------------------------
        _log("Extracting structured report…")
        report = await extract_structured_report(llm, session.history, SYSTEM_PROMPT)
        session.report = report

        # ------------------------------------------------------------------
        # 5. Living analysis document
        # ------------------------------------------------------------------
        cmd_name = deck.commander.name if deck.commander else "Unknown Commander"
        doc = DeckDocument.create(cmd_name, output_path=output_path)
        if report:
            doc.apply_initial_report(report)
        doc.write()
        session.document = doc

        return session, prose, report

    # ------------------------------------------------------------------
    # Multi-turn conversation
    # ------------------------------------------------------------------

    async def chat(
        self,
        user_message: str,
        progress: Progress | None = None,
    ) -> str:
        """Add a user turn and return the assistant's response."""
        def _log(msg: str) -> None:
            if progress:
                progress(msg)

        self.history.append(Message(role=Role.USER, content=user_message))
        _log("Thinking…")
        response = await self._run_agentic_loop(progress=_log)

        if self.document is not None:
            _log("Updating analysis document…")
            suggestions = await extract_chat_suggestions(self.llm, self.history, SYSTEM_PROMPT)
            note = user_message[:120] if len(user_message) > 120 else user_message
            self.document.merge_chat_suggestions(suggestions, note=note)
            self.document.write()

        return response

    # ------------------------------------------------------------------
    # Internal: agentic tool-use loop
    # ------------------------------------------------------------------

    async def _run_agentic_loop(self, progress: Progress | None = None) -> str:
        def _log(msg: str) -> None:
            if progress:
                progress(msg)

        scryfall = ScryfallClient()  # tools fall back to live Scryfall when cache misses

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self.llm.chat(
                self.history,
                system=SYSTEM_PROMPT,
                tools=ALL_TOOLS,
            )

            if not response.tool_calls:
                # Model finished — append and return
                self.history.append(
                    Message(role=Role.ASSISTANT, content=response.content)
                )
                return response.content or "No response."

            # Model wants tools — execute then feed results back
            _log(f"Using tools: {[tc.name for tc in response.tool_calls]}")
            self.history.append(Message(
                role=Role.ASSISTANT,
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            for tc in response.tool_calls:
                # Check cache before hitting Scryfall for lookup_card calls
                result = await _execute_with_cache(tc, self.cache, scryfall)
                self.history.append(Message(
                    role=Role.TOOL,
                    content=result,
                    tool_call_id=tc.id,
                ))

        # Safety cap — ask model to wrap up
        _log("Reached tool-call limit, requesting final answer…")
        self.history.append(Message(
            role=Role.USER,
            content="Please provide your final analysis now based on everything gathered.",
        ))
        final = await self.llm.chat(self.history, system=SYSTEM_PROMPT)
        self.history.append(Message(role=Role.ASSISTANT, content=final.content))
        return final.content or "Analysis incomplete."


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _cache_hit_count(cache: CardCache, names: list[str]) -> int:
    return sum(1 for n in names if cache.get_sync(n) is not None)


async def _execute_with_cache(tc, cache: CardCache, scryfall: ScryfallClient) -> str:
    """For lookup_card, try cache first before live Scryfall."""
    from src.tutor.tools import execute_tool

    if tc.name == "lookup_card":
        name = tc.arguments.get("name", "")
        cached = await cache.get(name)
        if cached:
            return cached.summary()
        # Miss — fetch live and populate cache
        try:
            card = await cache.fetch(name)
            return card.summary()
        except Exception:
            pass  # fall through to normal execute_tool

    return await execute_tool(tc, scryfall)


# ------------------------------------------------------------------
# Convenience function kept for backward compatibility
# ------------------------------------------------------------------

async def analyze_deck(
    deck: Deck,
    progress: Progress | None = None,
) -> str:
    """One-shot analysis — returns prose only. Use TutorSession for multi-turn."""
    _, prose, _ = await TutorSession.start(deck, progress=progress)
    return prose
