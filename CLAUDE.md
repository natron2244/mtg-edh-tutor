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

### No direct Scryfall calls outside `src/scryfall/`
All card data access goes through `ScryfallClient`. This keeps rate-limiting and caching centralized.

### Async throughout
All I/O is async (`httpx`, `asyncio`). CLI entry points use `asyncio.run()`.

## Tech Stack
- Python 3.12+, managed with `uv`
- `pydantic` for all data models
- `pydantic-settings` for config (reads `.env`)
- `typer` + `rich` for CLI
- `httpx` for async HTTP
- `pytest` + `pytest-asyncio` for tests

## Commands
```bash
# Install dependencies
uv sync

# Run CLI
uv run edh-tutor analyze <deck.txt>

# Tests
uv run pytest

# Type check
uv run mypy src/
```

## Environment
Copy `.env.example` to `.env` and set:
- `OLLAMA_BASE_URL` — default `http://localhost:11434`
- `OLLAMA_MODEL` — default `gemma4:26`
- `LLM_PROVIDER` — `ollama` or `claude`

## Project Phases
- Phase 1 (current): Foundation — LLM facade, Scryfall client, deck parser
- Phase 2: Core tutor CLI with agentic tool-use loop
- Phase 3: Multi-turn conversation, RAG, structured output
- Phase 4: FastAPI + web UI
