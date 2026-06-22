"""
Eval test cases for the EDH Tutor prompt.

Each EvalCase describes a decklist with intentional, known flaws and specifies:
  - expected_weakness_keywords: strings the code grader checks appear in weaknesses
  - expected_power_level_max/min: range the structured report should land in
  - min_suggestions: floor on how many card swaps the tutor should propose
  - known_issues: plain-English descriptions fed to the model grader as ground truth
"""
from pathlib import Path

from pydantic import BaseModel

DATASETS_DIR = Path(__file__).parent / "datasets"


class EvalCase(BaseModel):
    name: str
    description: str
    decklist_path: Path
    commander_override: str | None = None

    # Code-grader expectations
    expected_power_level_max: int | None = None
    expected_power_level_min: int | None = None
    expected_weakness_keywords: list[str] = []
    min_suggestions: int = 1

    # Model-grader ground truth
    known_issues: list[str] = []


EVAL_SUITE: list[EvalCase] = [
    EvalCase(
        name="krenko_ramp_light",
        description=(
            "Krenko, Mob Boss mono-red goblin deck with only 2 ramp pieces "
            "(Sol Ring + Fire Diamond) vs the recommended 10, and only 30 lands."
        ),
        decklist_path=DATASETS_DIR / "krenko_ramp_light.txt",
        expected_power_level_max=6,
        expected_weakness_keywords=["ramp", "mana"],
        min_suggestions=3,
        known_issues=[
            "The deck has only 2 ramp pieces (Sol Ring and Fire Diamond) instead of the recommended ~10.",
            "The deck has only 30 lands, below the recommended 36-38 for Commander.",
            "There is minimal card draw — the deck has no dedicated draw engines.",
        ],
    ),
    EvalCase(
        name="atraxa_land_light",
        description=(
            "Atraxa, Praetors' Voice 4-color proliferate deck with only 28 lands "
            "(recommended 36-38), making it highly susceptible to mana screw."
        ),
        decklist_path=DATASETS_DIR / "atraxa_land_light.txt",
        expected_power_level_max=7,
        expected_weakness_keywords=["land", "mana"],
        min_suggestions=2,
        known_issues=[
            "The deck has only 28 lands, far below the recommended 36-38 for a 4-color commander.",
            "A 4-color commander like Atraxa needs a more robust mana base to cast spells reliably.",
        ],
    ),
]
