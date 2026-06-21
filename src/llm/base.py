from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    role: Role
    content: str | None  # None when assistant responds with only tool calls
    tool_call_id: str | None = None  # populated when role == TOOL
    tool_calls: list["ToolCall"] = field(default_factory=list)  # populated when role == ASSISTANT


@dataclass
class ToolParameter:
    type: str
    description: str
    enum: list[str] | None = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, ToolParameter]
    required: list[str] = field(default_factory=list)

    def to_json_schema(self) -> dict[str, Any]:
        props = {
            k: {"type": v.type, "description": v.description}
            | ({"enum": v.enum} if v.enum else {})
            for k, v in self.parameters.items()
        }
        return {
            "type": "object",
            "properties": props,
            "required": self.required,
        }


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"


class LLMClient(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
        stream: bool = False,
        response_format: str | None = None,  # "json" to request JSON-only output
    ) -> LLMResponse: ...
