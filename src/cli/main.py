import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.status import Status

from src.deck import parse_decklist, parse_decklist_file
from src.tutor.agent import analyze_deck

app = typer.Typer(
    name="edh-tutor",
    help="AI-powered EDH/Commander deck tutor powered by Ollama.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def analyze(
    deck_file: Path = typer.Argument(
        ...,
        help="Path to a plain-text decklist file (MTGO / Moxfield format).",
        exists=True,
        readable=True,
    ),
    commander: Optional[str] = typer.Option(
        None,
        "--commander", "-c",
        help="Override / specify the commander name.",
    ),
) -> None:
    """Analyze a Commander deck and print improvement suggestions."""

    # Parse the deck
    try:
        deck = parse_decklist_file(str(deck_file), commander_override=commander)
    except Exception as e:
        console.print(f"[red]Failed to parse decklist:[/red] {e}")
        raise typer.Exit(1)

    cmd = deck.commander
    cmd_name = cmd.name if cmd else (commander or "unknown commander")
    console.print(Panel(
        f"[bold green]EDH Tutor[/bold green] — analyzing [cyan]{cmd_name}[/cyan] "
        f"([dim]{deck.total_cards} cards[/dim])",
        expand=False,
    ))

    result: str = ""
    error: Exception | None = None

    with Status("[bold yellow]Analyzing deck…[/bold yellow]", console=console, spinner="dots") as status:
        def on_progress(msg: str) -> None:
            status.update(f"[bold yellow]{msg}[/bold yellow]")

        try:
            result = asyncio.run(analyze_deck(deck, progress=on_progress))
        except Exception as e:
            error = e

    if error:
        console.print(f"[red]Analysis failed:[/red] {error}")
        raise typer.Exit(1)

    console.print()
    console.print(Markdown(result))


@app.command()
def ping() -> None:
    """Check that Ollama is reachable and the configured model is available."""
    import asyncio
    from src.config import settings
    from src.llm.ollama import OllamaClient

    client = OllamaClient(settings.ollama_base_url, settings.ollama_model)

    async def _ping() -> bool:
        return await client.ping()

    ok = asyncio.run(_ping())
    if ok:
        console.print(f"[green]✓[/green] Ollama is up — model [cyan]{settings.ollama_model}[/cyan] is available.")
    else:
        console.print(
            f"[red]✗[/red] Could not reach Ollama at [cyan]{settings.ollama_base_url}[/cyan] "
            f"or model [cyan]{settings.ollama_model}[/cyan] is not pulled.\n"
            f"Run: [bold]ollama pull {settings.ollama_model}[/bold]"
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
