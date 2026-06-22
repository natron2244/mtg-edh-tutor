"""
Eval runner — feeds each EvalCase through the full TutorSession pipeline
and grades the resulting DeckReport with both CodeGrader and ModelGrader.
"""
from dataclasses import dataclass, field

from src.deck import parse_decklist_file
from src.llm import get_client
from src.tutor.agent import TutorSession
from src.tutor.structured import DeckReport

from evals.cases import EVAL_SUITE, EvalCase
from evals.graders import CodeGrader, GradeResult, ModelGrader


@dataclass
class EvalResult:
    case: EvalCase
    report: DeckReport | None
    prose: str
    code_grade: GradeResult
    model_grade: GradeResult
    error: str | None = None

    @property
    def overall_passed(self) -> bool:
        return self.code_grade.passed and self.model_grade.passed

    @property
    def overall_score(self) -> float:
        return (self.code_grade.score + self.model_grade.score) / 2


async def run_case(
    case: EvalCase,
    code_grader: CodeGrader,
    model_grader: ModelGrader,
    progress_cb=None,
) -> EvalResult:
    def _log(msg: str) -> None:
        if progress_cb:
            progress_cb(f"[{case.name}] {msg}")

    _fail_grade = GradeResult(passed=False, score=0.0, details="Skipped due to error")

    try:
        deck = parse_decklist_file(
            str(case.decklist_path),
            commander_override=case.commander_override,
        )
    except Exception as exc:
        return EvalResult(
            case=case,
            report=None,
            prose="",
            code_grade=_fail_grade,
            model_grade=_fail_grade,
            error=f"Deck parse failed: {exc}",
        )

    try:
        _log("running tutor analysis…")
        session, prose, report = await TutorSession.start(deck, progress=_log)
    except Exception as exc:
        return EvalResult(
            case=case,
            report=None,
            prose="",
            code_grade=_fail_grade,
            model_grade=_fail_grade,
            error=f"TutorSession failed: {exc}",
        )

    _log("grading…")
    code_grade = code_grader.grade(case, report)
    model_grade = await model_grader.grade(case, report)

    return EvalResult(
        case=case,
        report=report,
        prose=prose,
        code_grade=code_grade,
        model_grade=model_grade,
    )


async def run_suite(
    cases: list[EvalCase] | None = None,
    progress_cb=None,
) -> list[EvalResult]:
    """Run every case sequentially; returns one EvalResult per case."""
    cases = cases or EVAL_SUITE
    llm = get_client()
    code_grader = CodeGrader()
    model_grader = ModelGrader(llm)

    results: list[EvalResult] = []
    for case in cases:
        result = await run_case(case, code_grader, model_grader, progress_cb=progress_cb)
        results.append(result)

    return results
