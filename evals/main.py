"""
EDH Tutor prompt eval runner.

Usage:
    uv run python -m evals.main                 # run full suite
    uv run python -m evals.main --case krenko_ramp_light   # single case
    uv run python -m evals.main --verbose        # show full grader details
"""
import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from evals.cases import EVAL_SUITE, EvalCase
from evals.runner import EvalResult, run_suite

app = typer.Typer(name="evals", help="Run prompt evals against the EDH Tutor.", no_args_is_help=False)
console = Console()


@app.command()
def main(
    case: Optional[str] = typer.Option(
        None, "--case", "-c",
        help="Run only this named case (default: run all).",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Print full grader output for each case.",
    ),
) -> None:
    """Evaluate the EDH Tutor prompt against test decklists with known flaws."""
    cases: list[EvalCase] = EVAL_SUITE
    if case:
        cases = [c for c in EVAL_SUITE if c.name == case]
        if not cases:
            names = ", ".join(c.name for c in EVAL_SUITE)
            console.print(f"[red]Unknown case '{case}'. Available: {names}[/red]")
            raise typer.Exit(1)

    console.print(Panel(
        f"[bold]EDH Tutor — Prompt Eval Suite[/bold]\n"
        f"[dim]Running {len(cases)} case(s) via Ollama model grader[/dim]",
        expand=False,
    ))

    results: list[EvalResult] = []

    def on_progress(msg: str) -> None:
        console.print(f"  [dim]{msg}[/dim]")

    try:
        results = asyncio.run(run_suite(cases, progress_cb=on_progress))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Eval run failed:[/red] {exc}")
        raise typer.Exit(1)

    _print_summary_table(results)

    if verbose:
        for r in results:
            _print_case_detail(r)

    passed = sum(1 for r in results if r.overall_passed)
    total = len(results)
    color = "green" if passed == total else "yellow" if passed > 0 else "red"
    console.print(f"\n[{color}]Result: {passed}/{total} cases passed[/{color}]")

    if passed < total:
        raise typer.Exit(1)


def _print_summary_table(results: list[EvalResult]) -> None:
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Case", no_wrap=True, min_width=24)
    table.add_column("Code", justify="center", min_width=12)
    table.add_column("Model", justify="center", min_width=12)
    table.add_column("Overall", justify="center", min_width=10)
    table.add_column("Power", justify="center", min_width=7)
    table.add_column("Suggestions", justify="center", min_width=11)

    for r in results:
        code_str = _grade_str(r.code_grade.passed, r.code_grade.score)
        model_str = _grade_str(r.model_grade.passed, r.model_grade.score)
        overall_str = _grade_str(r.overall_passed, r.overall_score)
        power_str = str(r.report.power_level) if r.report else "[red]N/A[/red]"
        sug_str = str(len(r.report.suggestions)) if r.report else "[red]N/A[/red]"
        error_note = f" [red](error)[/red]" if r.error else ""

        table.add_row(
            r.case.name + error_note,
            code_str,
            model_str,
            overall_str,
            power_str,
            sug_str,
        )

    console.print()
    console.print(table)


def _print_case_detail(r: EvalResult) -> None:
    console.print(f"\n[bold cyan]{'─' * 60}[/bold cyan]")
    console.print(f"[bold]{r.case.name}[/bold]  {r.case.description}")

    if r.error:
        console.print(f"[red]Error: {r.error}[/red]")
        return

    if r.report:
        console.print(
            f"[dim]Strategy:[/dim] {r.report.strategy_summary}  "
            f"[dim]Power:[/dim] {r.report.power_level}/10"
        )
        if r.report.weaknesses:
            console.print("[dim]Weaknesses:[/dim] " + "; ".join(r.report.weaknesses[:3]))

    console.print("\n[bold]Code Grader[/bold]")
    for line in r.code_grade.details.splitlines():
        color = "green" if line.startswith("PASS") else "red" if line.startswith("FAIL") else "dim"
        console.print(f"  [{color}]{line}[/{color}]")

    console.print("\n[bold]Model Grader[/bold]")
    for line in r.model_grade.details.splitlines():
        color = "green" if line.startswith("PASS") else "red" if line.startswith("FAIL") else "dim"
        console.print(f"  [{color}]{line}[/{color}]")


def _grade_str(passed: bool, score: float) -> str:
    color = "green" if passed else "red"
    label = "PASS" if passed else "FAIL"
    return f"[{color}]{label}[/{color}] [dim]({score:.0%})[/dim]"


if __name__ == "__main__":
    app()
