"""
LLM facade unit tests — no real model calls; tests shape/types only.
"""
import pytest
from src.llm.base import (
    LLMResponse,
    Message,
    Role,
    ToolCall,
    ToolDefinition,
    ToolParameter,
)
from src.llm.ollama import OllamaClient


def test_tool_definition_json_schema():
    tool = ToolDefinition(
        name="lookup_card",
        description="Look up a Magic card by name.",
        parameters={
            "name": ToolParameter(type="string", description="The card name"),
        },
        required=["name"],
    )
    schema = tool.to_json_schema()
    assert schema["type"] == "object"
    assert "name" in schema["properties"]
    assert schema["required"] == ["name"]


def test_message_role_values():
    assert Role.USER.value == "user"
    assert Role.ASSISTANT.value == "assistant"
    assert Role.TOOL.value == "tool"


def test_llm_response_defaults():
    resp = LLMResponse(content="hello")
    assert resp.tool_calls == []
    assert resp.stop_reason == "end_turn"


def test_tool_call_dataclass():
    tc = ToolCall(id="abc", name="lookup_card", arguments={"name": "Sol Ring"})
    assert tc.arguments["name"] == "Sol Ring"


def test_ollama_client_init():
    client = OllamaClient(base_url="http://localhost:11434", model="gemma4:26")
    assert client._model == "gemma4:26"


def test_ollama_encode_messages():
    client = OllamaClient(base_url="http://localhost:11434", model="gemma4:26")
    msgs = [Message(role=Role.USER, content="Hello")]
    encoded = client._encode_messages(msgs, system="Be helpful")
    assert encoded[0] == {"role": "system", "content": "Be helpful"}
    assert encoded[1] == {"role": "user", "content": "Hello"}
