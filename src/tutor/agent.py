"""
Main tutor agent — agentic loop that analyzes a deck and returns feedback.
"""
from collections.abc import Callable

from src.deck.models import Deck
from src.llm import get_client
from src.llm.base import Message, Role
from src.scryfall import ScryfallClient
from src.tutor.analysis import build_mana_curve, categorize_cards
from src.tutor.prompts import SYSTEM_PROMPT, format_deck_for_prompt
from src.tutor.tools import ALL_TOOLS, execute_tool

MAX_TOOL_ROUNDS = 10  # safety cap on agentic iterations


async def analyze_deck(
    deck: Deck,
    progress: Callable[[str], None] | None = None,
) -> str:
    """
    Analyze a deck and return a text report.

    Args:
        deck: Parsed Deck object.
        progress: Optional callback for progress updates (used by CLI spinner).

    Returns:
        The tutor's analysis as a markdown string.
    """
    def _log(msg: str) -> None:
        if progress:
            progress(msg)

    scryfall = ScryfallClient()
    llm = get_client()

    # ------------------------------------------------------------------
    # 1. Fetch card data for all cards upfront
    # ------------------------------------------------------------------
    _log("Fetching card data from Scryfall…")
    all_names = list(dict.fromkeys(deck.all_card_names))  # preserve order, dedupe
    card_data = await scryfall.get_cards_by_names(all_names)
    _log(f"Retrieved {len(card_data)}/{len(all_names)} cards from Scryfall.")

    # ------------------------------------------------------------------
    # 2. Run local analysis
    # ------------------------------------------------------------------
    fetched_cards = list(card_data.values())
    curve = build_mana_curve(fetched_cards)
    categories = categorize_cards(fetched_cards)

    # ------------------------------------------------------------------
    # 3. Build initial prompt
    # ------------------------------------------------------------------
    deck_summary = format_deck_for_prompt(deck, card_data, curve, categories)
    messages: list[Message] = [
        Message(role=Role.USER, content=deck_summary)
    ]

    # ------------------------------------------------------------------
    # 4. Agentic loop
    # ------------------------------------------------------------------
    _log("Running AI analysis (this may take a minute)…")
    for round_num in range(MAX_TOOL_ROUNDS):
        response = await llm.chat(
            messages,
            system=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
        )

        if not response.tool_calls:
            # Model finished — return its response
            return response.content or "No analysis returned."

        # Model wants to call tools — execute them and feed results back
        _log(f"Model is using tools: {[tc.name for tc in response.tool_calls]}")

        # Append the assistant turn (with tool calls) to history
        messages.append(Message(
            role=Role.ASSISTANT,
            content=response.content,
            tool_calls=response.tool_calls,
        ))

        # Execute each tool call and append results
        for tool_call in response.tool_calls:
            result = await execute_tool(tool_call, scryfall)
            messages.append(Message(
                role=Role.TOOL,
                content=result,
                tool_call_id=tool_call.id,
            ))

    # Exceeded max rounds — ask model to wrap up without more tools
    _log("Reached tool-call limit, requesting final answer…")
    messages.append(Message(
        role=Role.USER,
        content="Please provide your final analysis now based on everything you've gathered.",
    ))
    final = await llm.chat(messages, system=SYSTEM_PROMPT)
    return final.content or "Analysis incomplete."
