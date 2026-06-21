"""
Tool definitions and their handler functions.
These are the tools the LLM can call during deck analysis.
"""
import json

from src.scryfall import CardNotFoundError, ScryfallClient
from src.llm.base import ToolCall, ToolDefinition, ToolParameter

# ---------------------------------------------------------------------------
# Tool definitions (sent to the LLM)
# ---------------------------------------------------------------------------

LOOKUP_CARD = ToolDefinition(
    name="lookup_card",
    description=(
        "Look up a Magic: The Gathering card by name and return its oracle text, "
        "mana cost, type line, color identity, CMC, and price. "
        "Use this when you need details about a specific card."
    ),
    parameters={
        "name": ToolParameter(type="string", description="The exact or close card name to look up"),
    },
    required=["name"],
)

SEARCH_CARDS = ToolDefinition(
    name="search_cards",
    description=(
        "Search for Magic cards using a Scryfall query. "
        "Useful for finding replacement cards or cards that fit a specific role. "
        "Examples: 't:creature color<=G cmc<=3', 'o:proliferate', 'is:commander color=WUBG'. "
        "Returns up to 10 results."
    ),
    parameters={
        "query": ToolParameter(type="string", description="A Scryfall search query string"),
    },
    required=["query"],
)

ALL_TOOLS = [LOOKUP_CARD, SEARCH_CARDS]

# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def handle_lookup_card(args: dict, client: ScryfallClient) -> str:
    name = args.get("name", "")
    try:
        card = await client.get_card_by_name(name, exact=False)
        parts = [
            f"Name: {card.name}",
            f"Mana Cost: {card.mana_cost or 'N/A'}",
            f"CMC: {card.cmc}",
            f"Type: {card.type_line}",
            f"Color Identity: {''.join(card.color_identity) or 'Colorless'}",
            f"Oracle Text: {card.oracle_text or 'N/A'}",
            f"Commander Legal: {card.is_commander_legal}",
        ]
        if card.usd_price is not None:
            parts.append(f"Price (USD): ${card.usd_price:.2f}")
        return "\n".join(parts)
    except CardNotFoundError:
        return f"Card not found: {name!r}"
    except Exception as e:
        return f"Error looking up card: {e}"


async def handle_search_cards(args: dict, client: ScryfallClient) -> str:
    query = args.get("query", "")
    try:
        cards = await client.search_cards(query, limit=10)
        if not cards:
            return f"No cards found for query: {query!r}"
        lines = [f"Found {len(cards)} card(s) for query {query!r}:"]
        for card in cards:
            price = f" (${card.usd_price:.2f})" if card.usd_price is not None else ""
            lines.append(f"  • {card.name} {card.mana_cost or ''} — {card.type_line}{price}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching cards: {e}"


async def execute_tool(tool_call: ToolCall, scryfall: ScryfallClient) -> str:
    """Dispatch a tool call to its handler and return the result string."""
    if tool_call.name == "lookup_card":
        return await handle_lookup_card(tool_call.arguments, scryfall)
    if tool_call.name == "search_cards":
        return await handle_search_cards(tool_call.arguments, scryfall)
    return f"Unknown tool: {tool_call.name!r}"
