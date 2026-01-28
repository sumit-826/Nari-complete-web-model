"""
Klix - LangChain Integration Module
Provides LangChain-based LLM clients with support for Gemini and Ollama.
Enables LangGraph agents, chains, and advanced memory integration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from config import Config, ModelProvider, get_config


# ============================================================================
# LangChain Message Conversion
# ============================================================================

def messages_to_langchain(messages: list[dict[str, Any]]) -> list[BaseMessage]:
    """Convert our message format to LangChain messages."""
    lc_messages = []
    
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                # Convert tool calls to LangChain format
                lc_tool_calls = []
                for tc in tool_calls:
                    lc_tool_calls.append({
                        "id": tc.get("id", f"call_{tc.get('name', 'unknown')}"),
                        "name": tc.get("name", ""),
                        "args": tc.get("arguments", {}),
                    })
                lc_messages.append(AIMessage(content=content, tool_calls=lc_tool_calls))
            else:
                lc_messages.append(AIMessage(content=content))
        elif role == "tool":
            lc_messages.append(ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_call_id", ""),
                name=msg.get("name", ""),
            ))
    
    return lc_messages


def langchain_to_messages(lc_messages: list[BaseMessage]) -> list[dict[str, Any]]:
    """Convert LangChain messages to our message format."""
    messages = []
    
    for msg in lc_messages:
        if isinstance(msg, SystemMessage):
            messages.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            message_dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                message_dict["tool_calls"] = [
                    {
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "arguments": tc.get("args", {}),
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(message_dict)
        elif isinstance(msg, ToolMessage):
            messages.append({
                "role": "tool",
                "content": msg.content,
                "tool_call_id": msg.tool_call_id,
                "name": msg.name,
            })
    
    return messages


# ============================================================================
# LangChain Response Dataclass
# ============================================================================

@dataclass
class LangChainResponse:
    """Standardized response from LangChain LLM."""
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: Any = None
    
    @classmethod
    def from_ai_message(cls, msg: AIMessage) -> LangChainResponse:
        """Create response from AIMessage."""
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.get("id", f"call_{tc.get('name', 'unknown')}"),
                    "name": tc.get("name", ""),
                    "arguments": tc.get("args", {}),
                })
        
        # Extract usage if available
        usage = {}
        if hasattr(msg, "response_metadata") and msg.response_metadata:
            if "usage" in msg.response_metadata:
                usage = msg.response_metadata["usage"]
        
        return cls(
            content=msg.content if isinstance(msg.content, str) else "",
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            usage=usage,
            raw_response=msg,
        )


# ============================================================================
# LangChain LLM Client
# ============================================================================

class LangChainClient:
    """
    Unified LangChain client supporting both Gemini and Ollama.
    Provides tool binding, streaming, and async support.
    """
    
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or get_config()
        self._llm = None
        self._tools: list[BaseTool] = []
        self._initialize_llm()
    
    def _initialize_llm(self) -> None:
        """Initialize the appropriate LLM based on config."""
        if self.config.default_provider == ModelProvider.GEMINI:
            self._llm = ChatGoogleGenerativeAI(
                model=self.config.gemini_model,
                google_api_key=self.config.google_api_key,
                temperature=0.7,
                convert_system_message_to_human=False,
            )
        else:
            self._llm = ChatOllama(
                model=self.config.ollama_model,
                base_url=self.config.ollama_host,
                temperature=0.7,
            )
    
    @property
    def llm(self):
        """Get the underlying LangChain LLM."""
        return self._llm
    
    @property
    def llm_with_tools(self):
        """Get LLM with tools bound."""
        if self._tools:
            return self._llm.bind_tools(self._tools)
        return self._llm
    
    def bind_tools(self, tools: list[BaseTool]) -> None:
        """Bind tools to the LLM."""
        self._tools = tools
    
    def switch_provider(self, provider: ModelProvider | str) -> None:
        """Switch to a different provider."""
        if isinstance(provider, str):
            provider = ModelProvider(provider.lower())
        self.config.switch_provider(provider)
        self._initialize_llm()
    
    def switch_model(self, model: str) -> None:
        """Switch to a different model."""
        self.config.switch_model(model)
        self._initialize_llm()
    
    # ========================================================================
    # Chat Methods
    # ========================================================================
    
    async def chat(
        self,
        messages: list[dict[str, Any]] | list[BaseMessage],
        tools: list[BaseTool] | None = None,
        stream: bool = False,
    ) -> LangChainResponse | AsyncGenerator[str, None]:
        """
        Send chat messages and get a response.
        
        Args:
            messages: List of messages (dict or BaseMessage format)
            tools: Optional tools to use for this request
            stream: Whether to stream the response
            
        Returns:
            LangChainResponse or async generator for streaming
        """
        # Convert messages if needed
        if messages and isinstance(messages[0], dict):
            lc_messages = messages_to_langchain(messages)
        else:
            lc_messages = messages
        
        # Get LLM with tools
        llm = self._llm
        if tools:
            llm = llm.bind_tools(tools)
        elif self._tools:
            llm = self.llm_with_tools
        
        if stream:
            return self._stream_response(llm, lc_messages)
        
        # Non-streaming
        response = await llm.ainvoke(lc_messages)
        return LangChainResponse.from_ai_message(response)
    
    async def _stream_response(
        self,
        llm,
        messages: list[BaseMessage],
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens."""
        async for chunk in llm.astream(messages):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content
    
    def chat_sync(
        self,
        messages: list[dict[str, Any]] | list[BaseMessage],
        tools: list[BaseTool] | None = None,
    ) -> LangChainResponse:
        """Synchronous chat method."""
        # Convert messages if needed
        if messages and isinstance(messages[0], dict):
            lc_messages = messages_to_langchain(messages)
        else:
            lc_messages = messages
        
        # Get LLM with tools
        llm = self._llm
        if tools:
            llm = llm.bind_tools(tools)
        elif self._tools:
            llm = self.llm_with_tools
        
        response = llm.invoke(lc_messages)
        return LangChainResponse.from_ai_message(response)
    
    # ========================================================================
    # Simple Generation
    # ========================================================================
    
    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate a simple text response."""
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        
        response = await self._llm.ainvoke(messages)
        return response.content if isinstance(response.content, str) else ""
    
    def generate_sync(self, prompt: str, system: str | None = None) -> str:
        """Synchronous generation."""
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        
        response = self._llm.invoke(messages)
        return response.content if isinstance(response.content, str) else ""


# ============================================================================
# Factory Functions
# ============================================================================

def get_langchain_client(config: Config | None = None) -> LangChainClient:
    """Get a LangChain client instance."""
    return LangChainClient(config or get_config())


def get_langchain_llm(config: Config | None = None):
    """Get the raw LangChain LLM (ChatGoogleGenerativeAI or ChatOllama)."""
    config = config or get_config()
    
    if config.default_provider == ModelProvider.GEMINI:
        return ChatGoogleGenerativeAI(
            model=config.gemini_model,
            google_api_key=config.google_api_key,
            temperature=0.7,
        )
    else:
        return ChatOllama(
            model=config.ollama_model,
            base_url=config.ollama_host,
            temperature=0.7,
        )


# ============================================================================
# LangChain Tool Decorator Helper
# ============================================================================

def create_langchain_tool(
    name: str,
    description: str,
    func: callable,
) -> BaseTool:
    """
    Create a LangChain tool from a function.
    
    Example:
        def my_search(query: str) -> str:
            return f"Results for: {query}"
        
        search_tool = create_langchain_tool(
            name="search",
            description="Search the web",
            func=my_search,
        )
    """
    return tool(name=name, description=description)(func)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "LangChainClient",
    "LangChainResponse",
    "get_langchain_client",
    "get_langchain_llm",
    "create_langchain_tool",
    "messages_to_langchain",
    "langchain_to_messages",
]
