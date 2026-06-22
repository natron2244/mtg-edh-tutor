"""
DeckDocument — a living markdown file that tracks the tutor's analysis.

Sections update as you chat:
  - Deck Description  (set from initial DeckReport)
  - Strengths         (set from initial DeckReport, refined on chat)
  - Weaknesses        (set from initial DeckReport, refined on chat)
  - Cuts / Adds       (swap table, accumulates across all turns)
  - Notes             (one bullet per chat turn)
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.tutor.structured import Suggestion


def _commander_slug(name: str) -> str:
    """'Atraxa, Praetors\\' Voice' → 'atraxa_praetors_voice'"""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


@dataclass
class DeckDocument:
    commander_name: str
    path: Path
    strategy: str = ""
    power_level: int | None = None
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    swaps: list[Suggestion] = field(default_factory=list)  # cut + add + reason
    notes: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        commander_name: str,
        output_path: Path | None = None,
    ) -> "DeckDocument":
        if output_path is None:
            output_path = Path(f"{_commander_slug(commander_name)}_analysis.md")
        return cls(commander_name=commander_name, path=output_path)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def apply_initial_report(self, report) -> None:  # report: DeckReport
        self.strategy = report.strategy_summary
        self.power_level = report.power_level
        self.strengths = list(report.strengths)
        self.weaknesses = list(report.weaknesses)
        self._merge_swaps(report.suggestions)

    def merge_chat_suggestions(self, suggestions: list[Suggestion], note: str) -> None:
        """Add new swap suggestions from a chat turn and record a note."""
        self._merge_swaps(suggestions)
        if note:
            self.notes.append(note)

    def _merge_swaps(self, suggestions: list[Suggestion]) -> None:
        existing = {s.cut.lower() for s in self.swaps}
        for s in suggestions:
            if s.cut.lower() not in existing:
                self.swaps.append(s)
                existing.add(s.cut.lower())

    # ------------------------------------------------------------------
    # Rendering & I/O
    # ------------------------------------------------------------------

    def write(self) -> None:
        self.path.write_text(self._render(), encoding="utf-8")

    def _render(self) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines: list[str] = [
            f"# {self.commander_name} — Deck Analysis",
            "",
            f"_Last updated: {now}_",
            "",
        ]

        # Deck Description
        if self.strategy:
            pl = f"  _(Power level: {self.power_level}/10)_" if self.power_level else ""
            lines += [f"## Deck Description{pl}", "", self.strategy, ""]

        # Strengths
        if self.strengths:
            lines += ["## Strengths", ""]
            for s in self.strengths:
                lines.append(f"- {s}")
            lines.append("")

        # Weaknesses
        if self.weaknesses:
            lines += ["## Weaknesses", ""]
            for w in self.weaknesses:
                lines.append(f"- {w}")
            lines.append("")

        # Cuts & Adds (paired swap table)
        if self.swaps:
            lines += ["## Cuts & Adds", ""]
            lines.append("| Cut | Add | Reason |")
            lines.append("|-----|-----|--------|")
            for s in self.swaps:
                reason = s.reason.replace("|", "\\|")
                lines.append(f"| {s.cut} | {s.add} | {reason} |")
            lines.append("")

        # Notes
        if self.notes:
            lines += ["## Notes", ""]
            for note in self.notes:
                lines.append(f"- {note}")
            lines.append("")

        return "\n".join(lines)
