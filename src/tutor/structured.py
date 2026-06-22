"""
Structured analysis output — Pydantic models + JSON extraction from LLM.

After the prose analysis, a second LLM call asks the model to distill its
findings into a validated DeckReport. This gives callers a machine-readable
summary alongside the full markdown narrative.
"""
import json
import re

from pydantic import BaseModel, Field

from src.llm.base import LLMClient, Message, Role

EXTRACTION_PROMPT = """\
Based on your analysis above, extract the key findings as JSON matching this exact schema. \
Output ONLY valid JSON with no surrounding prose or markdown fences.

{
  "strategy_summary": "<one-sentence description of the deck's strategy>",
  "power_level": <integer 1-10>,
  "strengths": ["<strength 1>", "<strength 2>", ...],
  "weaknesses": ["<weakness 1>", "<weakness 2>", ...],
  "suggestions": [
    {"cut": "<card to remove>", "add": "<card to add>", "reason": "<why>"},
    ...
  ],
  "budget_notes": "<optional note about budget-friendly alternatives or null>"
}
"""


class Suggestion(BaseModel):
    cut: str = Field(description="Card name to remove from the deck")
    add: str = Field(description="Card name to add to the deck")
    reason: str = Field(description="Why this swap improves the deck")


class DeckReport(BaseModel):
    strategy_summary: str
    power_level: int = Field(ge=1, le=10)
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[Suggestion]
    budget_notes: str | None = None


def _extract_json(text: str) -> str:
    """Strip markdown fences and find the first JSON object in the text."""
    # Remove ```json ... ``` wrappers
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Find the outermost JSON object
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


CHAT_EXTRACTION_PROMPT = """\
From your response above, extract any specific card swap suggestions as JSON. \
Output ONLY valid JSON with no prose or markdown fences:
{"suggestions": [{"cut": "<card to remove>", "add": "<card to add>", "reason": "<why>"}]}
If there are no specific swaps, return {"suggestions": []}.
"""


async def extract_chat_suggestions(
    llm: LLMClient,
    conversation_history: list[Message],
    system: str,
) -> list[Suggestion]:
    """
    After a chat turn, distil any swap suggestions the model mentioned into a
    structured list. Returns [] on parse failure — treat as "no new suggestions."
    """
    messages = list(conversation_history) + [
        Message(role=Role.USER, content=CHAT_EXTRACTION_PROMPT)
    ]
    response = await llm.chat(messages, system=system, tools=None, response_format="json")
    raw = response.content or ""
    try:
        json_str = _extract_json(raw)
        data = json.loads(json_str)
        return [Suggestion.model_validate(s) for s in data.get("suggestions", [])]
    except Exception:
        return []


async def extract_structured_report(
    llm: LLMClient,
    conversation_history: list[Message],
    system: str,
) -> DeckReport | None:
    """
    Ask the LLM to distil its prior analysis into a structured DeckReport.
    Returns None if parsing fails — callers should treat prose as the fallback.
    """
    messages = list(conversation_history) + [
        Message(role=Role.USER, content=EXTRACTION_PROMPT)
    ]

    response = await llm.chat(
        messages,
        system=system,
        tools=None,
        response_format="json",
    )

    raw = response.content or ""
    try:
        json_str = _extract_json(raw)
        data = json.loads(json_str)
        return DeckReport.model_validate(data)
    except Exception:
        return None
