import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.table import Table

from src.deck import parse_decklist_file
from src.tutor.agent import TutorSession
from src.tutor.structured import DeckReport

app = typer.Typer(
    name="edh-tutor",
    help="AI-powered EDH/Commander deck tutor powered by Ollama.",
    no_args_is_help=True,
)
console = Console()

_CHAT_HELP = (
    "[dim]Ask a follow-up question, or type [bold]/help[/bold] for commands, "
    "[bold]/report[/bold] for the structured summary, [bold]/exit[/bold] to quit.[/dim]"
)


@app.command()
def analyze(
    deck_file: Path = typer.Argument(
        ...,
        help="Path to a plain-text decklist (MTGO / Moxfield format).",
        exists=True,
        readable=True,
    ),
    commander: Optional[str] = typer.Option(
        None, "--commander", "-c",
        help="Override / specify the commander name.",
    ),
    no_chat: bool = typer.Option(
        False, "--no-chat",
        help="Exit after the initial analysis (skip the interactive loop).",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Path for the living analysis markdown file (default: <commander>_analysis.md).",
    ),
) -> None:
    """Analyze a Commander deck, then enter an interactive Q&A session."""

    try:
        deck = parse_decklist_file(str(deck_file), commander_override=commander)
    except Exception as e:
        console.print(f"[red]Failed to parse decklist:[/red] {e}")
        raise typer.Exit(1)

    cmd = deck.commander
    cmd_name = cmd.name if cmd else (commander or "unknown commander")
    console.print(Panel(
        f"[bold green]EDH Tutor[/bold green] — [cyan]{cmd_name}[/cyan] "
        f"([dim]{deck.total_cards} cards[/dim])",
        expand=False,
    ))

    session: TutorSession | None = None
    prose: str = ""
    report: DeckReport | None = None
    error: Exception | None = None
    error_tb: str = ""

    with Status("[bold yellow]Analyzing deck…[/bold yellow]", console=console, spinner="dots") as status:
        def on_progress(msg: str) -> None:
            status.update(f"[bold yellow]{msg}[/bold yellow]")

        try:
            session, prose, report = asyncio.run(
                TutorSession.start(deck, progress=on_progress, output_path=output)
            )
        except Exception as e:
            import traceback
            error = e
            error_tb = traceback.format_exc()

    if error:
        console.print(f"[red]Analysis failed:[/red] {error!r}")
        console.print(error_tb)
        raise typer.Exit(1)

    console.print()
    console.print(Markdown(prose))

    if report:
        console.print()
        _print_report_panel(report)

    if session is not None and session.document is not None:
        console.print()
        console.print(f"[dim]Analysis saved to:[/dim] [cyan]{session.document.path}[/cyan]")

    if no_chat or session is None:
        return

    # ------------------------------------------------------------------
    # Interactive multi-turn loop
    # ------------------------------------------------------------------
    console.print()
    console.print(Panel(_CHAT_HELP, expand=False))

    while True:
        try:
            user_input = console.input("[bold cyan]You >[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            cmd_word = user_input.lstrip("/").lower().split()[0]

            if cmd_word in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if cmd_word == "help":
                console.print(
                    "[bold]Commands:[/bold]\n"
                    "  [cyan]/report[/cyan]   — print the structured analysis summary\n"
                    "  [cyan]/deck[/cyan]     — show the parsed deck list\n"
                    "  [cyan]/exit[/cyan]     — quit\n"
                    "  Anything else is sent to the AI as a question."
                )
                continue

            if cmd_word == "report":
                if report:
                    _print_report_panel(report)
                else:
                    console.print("[yellow]No structured report available.[/yellow]")
                continue

            if cmd_word == "deck":
                _print_deck_summary(deck)
                continue

            console.print(f"[yellow]Unknown command: {user_input!r}[/yellow]")
            continue

        # Regular question — send to the AI
        response: str = ""
        err: Exception | None = None

        with Status("[bold yellow]Thinking…[/bold yellow]", console=console, spinner="dots") as status:
            def _prog(msg: str) -> None:
                status.update(f"[bold yellow]{msg}[/bold yellow]")

            try:
                assert session is not None
                response = asyncio.run(session.chat(user_input, progress=_prog))
            except Exception as e:
                err = e

        if err:
            console.print(f"[red]Error:[/red] {err}")
        else:
            console.print()
            console.print(Markdown(response))
            if session.document is not None:
                console.print(f"[dim]✓ Document updated: {session.document.path}[/dim]")
            console.print()


@app.command()
def ping() -> None:
    """Check that Ollama is reachable and the configured model is available."""
    from src.config import settings
    from src.llm.ollama import OllamaClient

    client = OllamaClient(settings.ollama_base_url, settings.ollama_model)

    ok = asyncio.run(client.ping())
    if ok:
        console.print(
            f"[green]✓[/green] Ollama is up — model [cyan]{settings.ollama_model}[/cyan] is available."
        )
    else:
        console.print(
            f"[red]✗[/red] Could not reach Ollama at [cyan]{settings.ollama_base_url}[/cyan] "
            f"or model [cyan]{settings.ollama_model}[/cyan] is not pulled.\n"
            f"Run: [bold]ollama pull {settings.ollama_model}[/bold]"
        )
        raise typer.Exit(1)


# ------------------------------------------------------------------
# Rich helpers
# ------------------------------------------------------------------

def _print_report_panel(report: DeckReport) -> None:
    power_color = "green" if report.power_level >= 7 else "yellow" if report.power_level >= 4 else "red"
    console.print(Panel(
        f"[bold]Strategy:[/bold] {report.strategy_summary}\n"
        f"[bold]Power Level:[/bold] [{power_color}]{report.power_level}/10[/{power_color}]",
        title="[bold]Structured Report[/bold]",
        expand=False,
    ))

    if report.strengths:
        console.print("[bold green]Strengths[/bold green]")
        for s in report.strengths:
            console.print(f"  [green]+[/green] {s}")

    if report.weaknesses:
        console.print("[bold red]Weaknesses[/bold red]")
        for w in report.weaknesses:
            console.print(f"  [red]−[/red] {w}")

    if report.suggestions:
        table = Table(title="Suggestions", show_header=True, header_style="bold magenta")
        table.add_column("Cut", style="red", no_wrap=True)
        table.add_column("Add", style="green", no_wrap=True)
        table.add_column("Reason")
        for s in report.suggestions:
            table.add_row(s.cut, s.add, s.reason)
        console.print(table)

    if report.budget_notes:
        console.print(f"[dim]Budget notes: {report.budget_notes}[/dim]")


def _print_deck_summary(deck) -> None:
    from src.deck.models import Zone
    console.print(f"[bold]Total cards:[/bold] {deck.total_cards}")
    cmd = deck.commander
    if cmd:
        console.print(f"[bold]Commander:[/bold] {cmd.name}")
    console.print(f"[bold]Mainboard:[/bold] {len(deck.mainboard)} entries")


if __name__ == "__main__":
    app()
