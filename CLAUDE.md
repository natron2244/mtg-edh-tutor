# MTG EDH Tutor — Claude Code Project Guide

## Project Overview
AI-powered EDH/Commander deck tutor. Given a decklist, it evaluates the deck and suggests improvements using an LLM + Scryfall card data.

## Key Architecture Rules

### LLM Facade (critical)
All LLM calls MUST go through `src/llm/base.py:LLMClient`. Never import `OllamaClient` or `ClaudeClient` directly outside of `src/llm/`. Use the factory:
```python
from src.llm import get_client
client = get_client()
```
The active provider is set via `LLM_PROVIDER` env var (`ollama` | `claude`).

### Card cache is the only Scryfall entry point in the tutor
Inside `src/tutor/`, all card data goes through `CardCache` (`src/tutor/cache.py`), which wraps `ScryfallClient` and persists results to `~/.cache/edh-tutor/cards.json`. Never call `ScryfallClient` directly from agent or tool code — use `CardCache.fetch()` or `CardCache.prefetch()`.

Outside `src/tutor/`, call `ScryfallClient` directly (e.g. in tests).

### Async throughout
All I/O is async (`httpx`, `asyncio`). CLI entry points use `asyncio.run()`.

### Quantities matter in analysis
`build_mana_curve()` takes `list[tuple[int, Card]]` — quantity-card pairs — not a flat card list. Always build these from `deck.entries` so that e.g. 30 Mountains counts as 30 lands.

## Source Layout

```
evals/
├── datasets/
│   ├── krenko_ramp_light.txt  # 100-card Krenko deck — only 2 ramp pieces (flaw: needs ~10)
│   └── atraxa_land_light.txt  # 100-card Atraxa deck — only 28 lands (flaw: needs 36-38)
├── cases.py                   # EvalCase pydantic model + EVAL_SUITE list
├── graders.py                 # CodeGrader (structural checks) + ModelGrader (Ollama-as-judge)
├── runner.py                  # run_suite() — feeds cases through TutorSession then graders
└── main.py                    # CLI entry point

src/
├── config.py              # pydantic-settings — reads .env
├── llm/
│   ├── base.py            # LLMClient ABC, Message, ToolDefinition, LLMResponse
│   ├── ollama.py          # OllamaClient — POST /api/chat, tool-call round-trips
│   └── claude.py          # ClaudeClient stub (raises NotImplementedError)
├── scryfall/
│   ├── client.py          # ScryfallClient — rate-limited, retries 429s
│   └── models.py          # Card, CardLegalities, CardPrices (pydantic)
├── deck/
│   ├── parser.py          # parse_decklist / parse_decklist_file
│   └── models.py          # Deck, CardEntry, Zone
├── tutor/
│   ├── cache.py           # CardCache — in-memory + disk persistence (RAG layer)
│   ├── analysis.py        # build_mana_curve, categorize_cards (pure Python)
│   ├── prompts.py         # SYSTEM_PROMPT + format_deck_for_prompt
│   ├── structured.py      # DeckReport pydantic model + extract_structured_report
│   ├── tools.py           # LOOKUP_CARD, SEARCH_CARDS definitions + handlers
│   └── agent.py           # TutorSession — agentic loop + multi-turn chat
└── cli/
    └── main.py            # typer app: `analyze` (interactive) + `ping`
```

## Tech Stack
- Python 3.12+, managed with `uv`
- `pydantic` v2 for all data models
- `pydantic-settings` for config (reads `.env`)
- `typer` + `rich` for CLI
- `httpx` for async HTTP
- `pytest` + `pytest-asyncio` for tests

## Commands
```bash
# Install dependencies
uv sync

# Check Ollama is reachable and model is pulled
uv run edh-tutor ping

# Analyze a deck (interactive multi-turn Q&A after initial analysis)
uv run edh-tutor analyze <deck.txt>

# Analyze without entering interactive mode (useful for scripting)
uv run edh-tutor analyze <deck.txt> --no-chat

# Override the commander
uv run edh-tutor analyze <deck.txt> --commander "Atraxa, Praetors' Voice"

# Run tests (offline — no Scryfall or Ollama needed)
uv run pytest tests/ --ignore=tests/test_scryfall.py

# Run all tests including Scryfall integration
uv run pytest tests/

# Type check
uv run mypy src/

# Run prompt evals (requires Ollama running)
uv run python -m evals.main

# Run a single eval case
uv run python -m evals.main --case krenko_ramp_light

# Run evals with full grader output
uv run python -m evals.main --verbose
```

## Prompt Eval System

The `evals/` package tests the quality of `SYSTEM_PROMPT` + `DeckReport` output against decklists with known, intentional flaws.

**Two grading strategies:**
- `CodeGrader` — deterministic: checks `DeckReport.power_level` range, `weaknesses` contain expected keywords, `suggestions` count meets minimum
- `ModelGrader` — uses Ollama as a judge: given the `DeckReport` JSON and plain-English known issues, it scores whether each issue was identified

**Adding a new test case:**
1. Drop a `.txt` decklist (standard MTGO format) in `evals/datasets/`
2. Add an `EvalCase` to `EVAL_SUITE` in `evals/cases.py` with `expected_weakness_keywords`, `expected_power_level_max`, and `known_issues`

The eval runner calls `TutorSession.start()` for the full pipeline (Scryfall + Ollama), so Ollama must be running.

## Deck File Format
Standard MTGO / Moxfield plain-text format. Section headers (case-insensitive) are optional:

```
Commander
1 Kumano, Master Yamabushi

Deck
1 Sol Ring
30 Mountain
1 Jeska's Will
```

Recognized zone headers: `Commander`, `Deck` / `Main` / `Mainboard`, `Sideboard` / `Side`.
Unknown headers (e.g. `Ramp`, `Interaction`) are silently skipped — cards below them land in the mainboard.
Inline commander marker (`*CMDR* 1 Atraxa, Praetors' Voice`) is also supported.

## Environment
Copy `.env.example` to `.env` and set:
- `OLLAMA_BASE_URL` — default `http://localhost:11434`
- `OLLAMA_MODEL` — default `gemma4:26b`
- `LLM_PROVIDER` — `ollama` or `claude`

## Project Phases
- Phase 1 ✅: Foundation — LLM facade, Scryfall client, deck parser
- Phase 2 ✅: Core tutor CLI — agentic tool-use loop, Scryfall tools, system prompt
- Phase 3 ✅: RAG card cache, structured output (DeckReport), multi-turn conversation
- Phase 4: FastAPI + web UI
