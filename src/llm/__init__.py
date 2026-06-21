from src.config import settings
from .base import LLMClient, LLMResponse, Message, Role, ToolCall, ToolDefinition, ToolParameter


def get_client() -> LLMClient:
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        from .ollama import OllamaClient
        return OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    if provider == "claude":
        from .claude import ClaudeClient
        return ClaudeClient(model=settings.claude_model)
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Use 'ollama' or 'claude'.")


__all__ = [
    "get_client",
    "LLMClient",
    "LLMResponse",
    "Message",
    "Role",
    "ToolCall",
    "ToolDefinition",
    "ToolParameter",
]
