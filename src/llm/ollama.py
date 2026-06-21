import json
import uuid
from typing import Any

import httpx

from .base import LLMClient, LLMResponse, Message, Role, ToolCall, ToolDefinition


class OllamaClient(LLMClient):
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def chat(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
        stream: bool = False,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._encode_messages(messages, system),
            "stream": stream,
        }
        if tools:
            payload["tools"] = [self._encode_tool(t) for t in tools]

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return self._decode_response(data)

    def _encode_messages(
        self, messages: list[Message], system: str | None
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if system:
            result.append({"role": "system", "content": system})
        for msg in messages:
            if msg.role == Role.TOOL:
                result.append({
                    "role": "tool",
                    "content": msg.content,
                })
            else:
                result.append({"role": msg.role.value, "content": msg.content})
        return result

    def _encode_tool(self, tool: ToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.to_json_schema(),
            },
        }

    def _decode_response(self, data: dict[str, Any]) -> LLMResponse:
        message = data.get("message", {})
        content: str | None = message.get("content") or None
        raw_calls: list[dict[str, Any]] = message.get("tool_calls") or []

        tool_calls = []
        for call in raw_calls:
            fn = call.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
            tool_calls.append(ToolCall(
                id=call.get("id") or str(uuid.uuid4()),
                name=fn.get("name", ""),
                arguments=args,
            ))

        stop_reason = "tool_use" if tool_calls else data.get("done_reason", "end_turn")
        return LLMResponse(content=content, tool_calls=tool_calls, stop_reason=stop_reason)

    async def ping(self) -> bool:
        """Return True if Ollama is reachable and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                resp.raise_for_status()
                tags = resp.json()
                models = [m["name"] for m in tags.get("models", [])]
                return any(self._model in m for m in models)
        except Exception:
            return False
