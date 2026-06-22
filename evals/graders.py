"""
Graders for the EDH Tutor prompt eval system.

Two grading strategies (mirrors the Anthropic eval course):

  CodeGrader   — fast, deterministic checks on DeckReport fields
  ModelGrader  — uses the Ollama LLM as a judge to assess whether the tutor
                 identified known deck issues expressed in plain English
"""
import json
import re
from dataclasses import dataclass

from src.llm.base import LLMClient, Message, Role
from src.tutor.structured import DeckReport

from evals.cases import EvalCase


@dataclass
class GradeResult:
    passed: bool
    score: float       # 0.0 – 1.0
    details: str       # human-readable breakdown of what passed/failed


# ---------------------------------------------------------------------------
# Code grader
# ---------------------------------------------------------------------------

class CodeGrader:
    """
    Deterministic checks against the structured DeckReport.

    Checks run:
      - DeckReport parsed (not None)
      - power_level within expected range
      - each expected_weakness_keyword appears somewhere in reported weaknesses
      - number of suggestions >= min_suggestions
    """

    def grade(self, case: EvalCase, report: DeckReport | None) -> GradeResult:
        if report is None:
            return GradeResult(
                passed=False,
                score=0.0,
                details="FAIL: DeckReport is None — structured extraction failed",
            )

        checks: list[tuple[bool, str]] = []

        if case.expected_power_level_max is not None:
            ok = report.power_level <= case.expected_power_level_max
            checks.append((ok, f"power_level {report.power_level} <= {case.expected_power_level_max}"))

        if case.expected_power_level_min is not None:
            ok = report.power_level >= case.expected_power_level_min
            checks.append((ok, f"power_level {report.power_level} >= {case.expected_power_level_min}"))

        weakness_text = " ".join(report.weaknesses).lower()
        for kw in case.expected_weakness_keywords:
            ok = kw.lower() in weakness_text
            checks.append((ok, f"weaknesses mention '{kw}'"))

        ok = len(report.suggestions) >= case.min_suggestions
        checks.append((ok, f"{len(report.suggestions)} suggestions >= {case.min_suggestions}"))

        passed_count = sum(1 for ok, _ in checks if ok)
        score = passed_count / len(checks) if checks else 1.0

        lines = [
            f"{'PASS' if ok else 'FAIL'}: {desc}"
            for ok, desc in checks
        ]
        return GradeResult(
            passed=score >= 0.75,
            score=score,
            details="\n".join(lines),
        )


# ---------------------------------------------------------------------------
# Model grader
# ---------------------------------------------------------------------------

_GRADER_SYSTEM = (
    "You are a precise evaluator of AI-generated Magic: The Gathering deck analyses. "
    "You respond only with valid JSON, no prose."
)

_GRADER_PROMPT = """\
Evaluate whether the AI deck analysis identified the following known issues:

Known issues:
{known_issues}

AI-produced DeckReport (JSON):
{report_json}

For each known issue, determine if the report addresses it.
Return ONLY valid JSON with this exact schema:

{{
  "findings": [
    {{
      "issue": "<known issue text>",
      "identified": true | false,
      "evidence": "<direct quote from report, or 'not found'>"
    }}
  ],
  "score": <float 0.0-1.0, fraction of issues identified>,
  "reasoning": "<one sentence overall assessment>"
}}"""


class ModelGrader:
    """
    Uses the active LLM (Ollama by default) as a judge.

    The grader receives the DeckReport JSON and a list of known issues,
    and returns a structured score with per-issue findings.
    """

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def grade(self, case: EvalCase, report: DeckReport | None) -> GradeResult:
        if report is None:
            return GradeResult(
                passed=False,
                score=0.0,
                details="FAIL: DeckReport is None — nothing to grade",
            )

        if not case.known_issues:
            return GradeResult(passed=True, score=1.0, details="No known issues defined — skipped")

        prompt = _GRADER_PROMPT.format(
            known_issues="\n".join(f"- {issue}" for issue in case.known_issues),
            report_json=report.model_dump_json(indent=2),
        )

        response = await self.llm.chat(
            [Message(role=Role.USER, content=prompt)],
            system=_GRADER_SYSTEM,
            tools=None,
            response_format="json",
        )

        raw = response.content or "{}"
        try:
            data = json.loads(_extract_json(raw))
            score = float(data.get("score", 0.0))
            reasoning = data.get("reasoning", "")
            findings = data.get("findings", [])

            lines = [
                f"{'PASS' if f.get('identified') else 'FAIL'}: {f.get('issue', '')}\n"
                f"       evidence: {f.get('evidence', 'not found')}"
                for f in findings
            ]
            lines.append(f"Reasoning: {reasoning}")

            return GradeResult(
                passed=score >= 0.6,
                score=score,
                details="\n".join(lines),
            )
        except Exception as exc:
            return GradeResult(
                passed=False,
                score=0.0,
                details=f"FAIL: grader parse error — {exc}\nRaw output: {raw[:300]}",
            )


def _extract_json(text: str) -> str:
    """Strip markdown fences and return the first JSON object found."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
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
                return text[start: i + 1]
    return text[start:]
