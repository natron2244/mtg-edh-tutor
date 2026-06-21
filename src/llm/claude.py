"""
ClaudeClient — drop-in swap for OllamaClient when LLM_PROVIDER=claude.
Requires: ANTHROPIC_API_KEY set in environment.
"""
from .base import LLMClient, LLMResponse, Message, ToolDefinition


class ClaudeClient(LLMClient):
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        import anthropic  # deferred so missing key doesn't break ollama usage
        self._client = anthropic.AsyncAnthropic()
        self._model = model

    async def chat(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
        stream: bool = False,
    ) -> LLMResponse:
        raise NotImplementedError(
            "ClaudeClient is a future integration. Set LLM_PROVIDER=ollama to use Ollama."
        )
