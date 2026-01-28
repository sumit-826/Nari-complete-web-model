"""
Klix - Memory Service using Mem0
Provides persistent, personalized memory layer for the AI agent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from mem0 import MemoryClient

from config import Config, get_config


class MemoryType(Enum):
    """Types of memories stored."""
    EPISODIC = "episodic"      # Specific past events/conversations
    SEMANTIC = "semantic"       # User preferences & facts
    PROCEDURAL = "procedural"   # How-to knowledge & patterns


@dataclass
class Memory:
    """Represents a single memory."""
    id: str
    content: str
    memory_type: MemoryType = MemoryType.EPISODIC
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_mem0(cls, data: dict[str, Any]) -> Memory:
        """Create Memory from mem0 API response."""
        memory_type = MemoryType.EPISODIC
        if metadata := data.get("metadata", {}):
            if type_str := metadata.get("type"):
                try:
                    memory_type = MemoryType(type_str)
                except ValueError:
                    pass
        
        return cls(
            id=data.get("id", ""),
            content=data.get("memory", ""),
            memory_type=memory_type,
            metadata=data.get("metadata", {}),
        )


@dataclass
class MemoryService:
    """
    Persistent memory layer using Mem0.
    
    Provides semantic search and storage of memories across sessions.
    Memories are stored per-user and can be scoped to projects.
    """
    
    config: Config = field(default_factory=get_config)
    _client: MemoryClient | None = field(default=None, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize the mem0 client."""
        api_key = self.config.mem0_api_key
        if api_key:
            self._client = MemoryClient(api_key=api_key)
    
    @property
    def is_enabled(self) -> bool:
        """Check if memory service is enabled and configured."""
        return self._client is not None and self.config.memory_enabled
    
    def _get_filters(self, user_id: str) -> dict[str, str]:
        """Build filters dict for mem0 API calls."""
        return {"user_id": user_id}
    
    # =========================================================================
    # Core Memory Operations
    # =========================================================================
    
    def search(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """
        Search for relevant memories using semantic similarity.
        
        Args:
            query: The search query
            user_id: User identifier (defaults to config)
            limit: Maximum number of results
            
        Returns:
            List of relevant memories
        """
        if not self.is_enabled:
            return []
        
        user_id = user_id or self.config.memory_user_id
        filters = self._get_filters(user_id)
        
        try:
            result = self._client.search(
                query=query,
                user_id=user_id,
                limit=limit,
                filters=filters,
            )
            
            memories = []
            for item in result.get("results", []):
                memories.append(Memory.from_mem0(item))
            return memories
            
        except Exception as e:
            print(f"[Memory] Search error: {e}")
            return []
    
    def get_all(
        self,
        user_id: str | None = None,
        limit: int = 20,
    ) -> list[Memory]:
        """
        Get all memories for a user.
        
        Args:
            user_id: User identifier (defaults to config)
            limit: Maximum number of results
            
        Returns:
            List of all memories
        """
        if not self.is_enabled:
            return []
        
        user_id = user_id or self.config.memory_user_id
        filters = self._get_filters(user_id)
        
        try:
            result = self._client.get_all(
                user_id=user_id,
                filters=filters,
            )
            
            memories = []
            for item in result.get("results", [])[:limit]:
                memories.append(Memory.from_mem0(item))
            return memories
            
        except Exception as e:
            print(f"[Memory] Get all error: {e}")
            return []
    
    def add(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None,
        memory_type: MemoryType = MemoryType.EPISODIC,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Add a conversation exchange to memory.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            user_id: User identifier (defaults to config)
            memory_type: Type of memory to store
            metadata: Additional metadata to store
            
        Returns:
            True if successful
        """
        if not self.is_enabled:
            return False
        
        user_id = user_id or self.config.memory_user_id
        
        # Build metadata
        mem_metadata = metadata or {}
        mem_metadata["type"] = memory_type.value
        mem_metadata["timestamp"] = datetime.now().isoformat()
        
        try:
            self._client.add(
                messages=messages,
                user_id=user_id,
                metadata=mem_metadata,
            )
            return True
            
        except Exception as e:
            print(f"[Memory] Add error: {e}")
            return False
    
    def add_text(
        self,
        text: str,
        user_id: str | None = None,
        memory_type: MemoryType = MemoryType.SEMANTIC,
    ) -> bool:
        """
        Add a simple text memory (for /remember command).
        
        Args:
            text: The memory text to store
            user_id: User identifier
            memory_type: Type of memory
            
        Returns:
            True if successful
        """
        if not self.is_enabled:
            return False
        
        user_id = user_id or self.config.memory_user_id
        
        try:
            self._client.add(
                messages=[{"role": "user", "content": text}],
                user_id=user_id,
                metadata={
                    "type": memory_type.value,
                    "source": "manual",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return True
            
        except Exception as e:
            print(f"[Memory] Add text error: {e}")
            return False
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete a specific memory by ID.
        
        Args:
            memory_id: The memory ID to delete
            
        Returns:
            True if successful
        """
        if not self.is_enabled:
            return False
        
        try:
            self._client.delete(memory_id=memory_id)
            return True
        except Exception as e:
            print(f"[Memory] Delete error: {e}")
            return False
    
    def delete_all(self, user_id: str | None = None) -> bool:
        """
        Delete all memories for a user.
        
        Args:
            user_id: User identifier (defaults to config)
            
        Returns:
            True if successful
        """
        if not self.is_enabled:
            return False
        
        user_id = user_id or self.config.memory_user_id
        
        try:
            self._client.delete_all(user_id=user_id)
            return True
        except Exception as e:
            print(f"[Memory] Delete all error: {e}")
            return False
    
    # =========================================================================
    # Context Building
    # =========================================================================
    
    def get_memory_context(
        self,
        query: str,
        user_id: str | None = None,
        max_memories: int = 5,
    ) -> str:
        """
        Build a context string from relevant memories for LLM injection.
        
        This is the main method used by the agent to retrieve memories
        before sending a prompt to the LLM.
        
        Args:
            query: The user's current query
            user_id: User identifier
            max_memories: Maximum memories to include
            
        Returns:
            Formatted string of relevant memories, or empty string
        """
        if not self.is_enabled:
            return ""
        
        user_id = user_id or self.config.memory_user_id
        
        # First try semantic search
        memories = self.search(query, user_id=user_id, limit=max_memories)
        
        # Fallback to recent memories if search returns nothing
        if not memories:
            memories = self.get_all(user_id=user_id, limit=max_memories)
        
        if not memories:
            return ""
        
        # Format memories for context
        lines = []
        for mem in memories:
            type_icon = {
                MemoryType.EPISODIC: "📅",
                MemoryType.SEMANTIC: "💡", 
                MemoryType.PROCEDURAL: "⚙️",
            }.get(mem.memory_type, "•")
            lines.append(f"{type_icon} {mem.content}")
        
        return "\n".join(lines)
    
    def extract_and_store(
        self,
        user_input: str,
        assistant_response: str,
        user_id: str | None = None,
    ) -> bool:
        """
        Extract and store memories from a conversation exchange.
        
        Called automatically after each exchange if auto_extract is enabled.
        Mem0 handles the extraction - we just need to pass the messages.
        
        Args:
            user_input: The user's message
            assistant_response: The assistant's response
            user_id: User identifier
            
        Returns:
            True if successful
        """
        if not self.is_enabled:
            return False
        
        messages = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": assistant_response},
        ]
        
        return self.add(
            messages=messages,
            user_id=user_id,
            memory_type=MemoryType.EPISODIC,
        )
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_stats(self, user_id: str | None = None) -> dict[str, Any]:
        """Get memory statistics for a user."""
        if not self.is_enabled:
            return {"enabled": False}
        
        user_id = user_id or self.config.memory_user_id
        memories = self.get_all(user_id=user_id, limit=100)
        
        # Count by type
        type_counts = {t: 0 for t in MemoryType}
        for mem in memories:
            type_counts[mem.memory_type] += 1
        
        return {
            "enabled": True,
            "user_id": user_id,
            "total_memories": len(memories),
            "by_type": {t.value: count for t, count in type_counts.items()},
        }


# =============================================================================
# Module-level convenience functions
# =============================================================================

_memory_service: MemoryService | None = None


def get_memory_service(config: Config | None = None) -> MemoryService:
    """Get or create the global MemoryService instance."""
    global _memory_service
    
    if _memory_service is None:
        _memory_service = MemoryService(config=config or get_config())
    
    return _memory_service


def reset_memory_service() -> None:
    """Reset the global MemoryService (for testing)."""
    global _memory_service
    _memory_service = None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "Memory",
    "MemoryType",
    "MemoryService",
    "get_memory_service",
    "reset_memory_service",
]