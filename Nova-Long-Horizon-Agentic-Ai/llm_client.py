"""
Gemini Code - LLM Client Abstraction Layer
Provides abstract adapter pattern for Gemini and Ollama backends.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable

from google import genai
from google.genai import types
import ollama

from config import Config, ModelProvider, get_config


@dataclass
class Message:
    """Represents a chat message."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # For tool responses


@dataclass
class ToolDefinition:
    """Definition of a tool for LLM function calling."""
    name: str
    description: str
    parameters: dict[str, Any]
    function: Callable[..., str] | None = None
    
    def to_gemini_format(self) -> types.FunctionDeclaration:
        """Convert to Gemini function declaration format."""
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )
    
    def to_ollama_format(self) -> dict[str, Any]:
        """Convert to Ollama tools format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


@dataclass
class LLMResponse:
    """Standardized response from LLM."""
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: Any = None


class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self._system_instruction: str = ""
    
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """Send chat messages and get a response."""
        pass
    
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate a simple text response."""
        pass
    
    def set_system_instruction(self, instruction: str) -> None:
        """Set the system instruction for the model."""
        self._system_instruction = instruction
    
    @property
    def system_instruction(self) -> str:
        return self._system_instruction or self._default_system_instruction()
    
    def _default_system_instruction(self) -> str:
        """Default system instruction for Klix."""
        return """You are Klix, an expert AI coding assistant with persistent memory. You help developers with:
- Writing, debugging, and refactoring code
- Explaining complex concepts clearly
- Suggesting best practices and optimizations
- Navigating and understanding codebases

You have access to tools for file operations and web search. Use them when appropriate.
Always be concise, accurate, and helpful. Format code with proper syntax highlighting.
When making changes to files, explain what you're doing and why.
You remember past conversations and user preferences - use this context to personalize your assistance."""


class GeminiClient(LLMClient):
    """Google Gemini API client using the new google-genai SDK."""
    
    def __init__(self, config: Config) -> None:
        super().__init__(config)
        
        # Configure the Gemini client
        self.client = genai.Client(api_key=config.google_api_key)
        self.model_name = config.gemini_model
        
        # Safety settings - set to BLOCK_NONE for developer freedom
        self.safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF",
            ),
        ]
    
    def _convert_messages_to_gemini(self, messages: list[Message]) -> list[types.Content]:
        """Convert messages to Gemini format."""
        gemini_messages = []
        
        for msg in messages:
            if msg.role == "system":
                continue  # System handled via system_instruction
            
            role = "user" if msg.role == "user" else "model"
            
            if msg.tool_calls:
                # Handle function calls
                parts = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                for tc in msg.tool_calls:
                    parts.append(types.Part.from_function_call(
                        name=tc["name"],
                        args=tc.get("arguments", {}),
                    ))
                gemini_messages.append(types.Content(role=role, parts=parts))
            elif msg.role == "tool":
                # Tool response
                gemini_messages.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=msg.name,
                        response={"result": msg.content},
                    )]
                ))
            else:
                gemini_messages.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.content)]
                ))
        
        return gemini_messages
    
    def _create_tools_config(self, tools: list[ToolDefinition]) -> list[types.Tool]:
        """Create Gemini tools configuration."""
        if not tools:
            return []
        
        function_declarations = [tool.to_gemini_format() for tool in tools]
        return [types.Tool(function_declarations=function_declarations)]
    
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """Send chat messages to Gemini."""
        
        # Extract system instruction from messages (includes memory context)
        system_content = self.system_instruction
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
                break
        
        gemini_messages = self._convert_messages_to_gemini(messages)
        tools_config = self._create_tools_config(tools) if tools else None
        
        # Build generation config with the system content from messages
        generate_config = types.GenerateContentConfig(
            system_instruction=system_content,
            safety_settings=self.safety_settings,
            tools=tools_config,
        )
        
        if stream:
            return self._stream_response(gemini_messages, generate_config)
        
        # Non-streaming response
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=gemini_messages,
            config=generate_config,
        )
        
        return self._parse_response(response)
    
    async def _stream_response(
        self,
        messages: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> AsyncGenerator[str, None]:
        """Stream response from Gemini."""
        response_stream = await asyncio.to_thread(
            self.client.models.generate_content_stream,
            model=self.model_name,
            contents=messages,
            config=config,
        )
        
        for chunk in response_stream:
            if chunk.text:
                yield chunk.text
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Gemini response to standardized format."""
        content = ""
        tool_calls = []
        
        if response.candidates:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    content += part.text
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append({
                        "id": f"call_{fc.name}",
                        "name": fc.name,
                        "arguments": dict(fc.args) if fc.args else {},
                    })
        
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "prompt_tokens": getattr(um, "prompt_token_count", 0),
                "completion_tokens": getattr(um, "candidates_token_count", 0),
                "total_tokens": getattr(um, "total_token_count", 0),
            }
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            usage=usage,
            raw_response=response,
        )
    
    async def generate(self, prompt: str) -> str:
        """Generate a simple text response."""
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                safety_settings=self.safety_settings,
            ),
        )
        return response.text if response.text else ""


class OllamaClient(LLMClient):
    """Ollama local LLM client."""
    
    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.client = ollama.Client(host=config.ollama_host)
        self.model_name = config.ollama_model
    
    def _convert_messages_to_ollama(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert messages to Ollama format."""
        ollama_messages = []
        
        # Extract system message from the passed messages (includes memory context)
        system_content = self.system_instruction
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
                break
        
        # Add system message with memory context
        if system_content:
            ollama_messages.append({
                "role": "system",
                "content": system_content,
            })
        
        for msg in messages:
            if msg.role == "system":
                continue  # Already handled above
            
            message_dict: dict[str, Any] = {
                "role": msg.role if msg.role != "tool" else "tool",
                "content": msg.content,
            }
            
            if msg.tool_calls:
                message_dict["tool_calls"] = [
                    {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc.get("arguments", {}),
                        }
                    }
                    for tc in msg.tool_calls
                ]
            
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
            
            ollama_messages.append(message_dict)
        
        return ollama_messages
    
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """Send chat messages to Ollama."""
        
        ollama_messages = self._convert_messages_to_ollama(messages)
        ollama_tools = [tool.to_ollama_format() for tool in tools] if tools else None
        
        if stream:
            return self._stream_response(ollama_messages, ollama_tools)
        
        # Non-streaming response
        response = await asyncio.to_thread(
            self.client.chat,
            model=self.model_name,
            messages=ollama_messages,
            tools=ollama_tools,
        )
        
        return self._parse_response(response)
    
    async def _stream_response(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> AsyncGenerator[str, None]:
        """Stream response from Ollama."""
        stream = await asyncio.to_thread(
            self.client.chat,
            model=self.model_name,
            messages=messages,
            tools=tools,
            stream=True,
        )
        
        for chunk in stream:
            if chunk.get("message", {}).get("content"):
                yield chunk["message"]["content"]
    
    def _parse_response(self, response: dict[str, Any]) -> LLMResponse:
        """Parse Ollama response to standardized format."""
        message = response.get("message", {})
        content = message.get("content", "")
        
        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                tool_calls.append({
                    "id": tc.get("id", f"call_{func.get('name', 'unknown')}"),
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", {}),
                })
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            usage={
                "prompt_tokens": response.get("prompt_eval_count", 0),
                "completion_tokens": response.get("eval_count", 0),
                "total_tokens": response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
            },
            raw_response=response,
        )
    
    async def generate(self, prompt: str) -> str:
        """Generate a simple text response."""
        response = await asyncio.to_thread(
            self.client.generate,
            model=self.model_name,
            prompt=f"{self.system_instruction}\n\n{prompt}" if self.system_instruction else prompt,
        )
        return response.get("response", "")


def get_client(provider: ModelProvider | str | None = None, config: Config | None = None) -> LLMClient:
    """
    Factory function to get the appropriate LLM client.
    
    Args:
        provider: The provider to use (gemini or ollama). If None, uses config default.
        config: Configuration object. If None, uses global config.
    
    Returns:
        An instance of the appropriate LLM client.
    """
    config = config or get_config()
    
    if provider is None:
        provider = config.default_provider
    elif isinstance(provider, str):
        provider = ModelProvider(provider.lower())
    
    if provider == ModelProvider.GEMINI:
        return GeminiClient(config)
    else:
        return OllamaClient(config)


def get_gemini_client(config: Config | None = None) -> GeminiClient:
    """Get a Gemini client instance."""
    return GeminiClient(config or get_config())


def get_ollama_client(config: Config | None = None) -> OllamaClient:
    """Get an Ollama client instance."""
    return OllamaClient(config or get_config())
