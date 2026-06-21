from pydantic import BaseModel, Field


class CardLegalities(BaseModel):
    commander: str = "not_legal"
    standard: str = "not_legal"
    modern: str = "not_legal"
    legacy: str = "not_legal"
    vintage: str = "not_legal"


class CardPrices(BaseModel):
    usd: str | None = None
    usd_foil: str | None = None
    eur: str | None = None


class Card(BaseModel):
    id: str
    name: str
    mana_cost: str | None = None
    cmc: float = 0.0
    type_line: str = ""
    oracle_text: str | None = None
    colors: list[str] = Field(default_factory=list)
    color_identity: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    legalities: CardLegalities = Field(default_factory=CardLegalities)
    prices: CardPrices = Field(default_factory=CardPrices)
    scryfall_uri: str = ""
    power: str | None = None
    toughness: str | None = None

    @property
    def is_commander_legal(self) -> bool:
        return self.legalities.commander == "legal"

    @property
    def usd_price(self) -> float | None:
        if self.prices.usd:
            try:
                return float(self.prices.usd)
            except ValueError:
                return None
        return None

    def summary(self) -> str:
        """Compact one-line description for LLM context."""
        parts = [self.name]
        if self.mana_cost:
            parts.append(f"({self.mana_cost})")
        parts.append(self.type_line)
        if self.oracle_text:
            # Truncate long oracle text
            text = self.oracle_text.replace("\n", " ")
            parts.append(f"— {text[:200]}{'…' if len(text) > 200 else ''}")
        return " ".join(parts)
