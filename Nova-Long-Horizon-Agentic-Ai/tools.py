"""
Gemini Code - Tools Registry and Implementations
Decorator-based tool registry for file system operations and web search.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

# Try to import duckduckgo_search, fallback to stub if not available
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

# Try to import Tavily, fallback to stub if not available
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

from config import get_config


# Type variable for tool functions
F = TypeVar("F", bound=Callable[..., str])


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    """Represents a registered tool."""
    name: str
    description: str
    function: Callable[..., str]
    parameters: list[ToolParameter] = field(default_factory=list)
    
    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema format for LLM function calling."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    
    def execute(self, **kwargs: Any) -> str:
        """Execute the tool with given arguments."""
        return self.function(**kwargs)


class ToolRegistry:
    """
    Registry for all available tools.
    Tools are registered using the @tool decorator.
    """
    
    _instance: ToolRegistry | None = None
    
    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance
    
    def __init__(self) -> None:
        if not hasattr(self, "_tools"):
            self._tools: dict[str, Tool] = {}
    
    def register(
        self,
        name: str,
        description: str,
        parameters: list[ToolParameter] | None = None,
    ) -> Callable[[F], F]:
        """
        Decorator to register a tool.
        
        Usage:
            @registry.register("tool_name", "Tool description", [params])
            def my_tool(arg1: str) -> str:
                return "result"
        """
        def decorator(func: F) -> F:
            tool = Tool(
                name=name,
                description=description,
                function=func,
                parameters=parameters or [],
            )
            self._tools[name] = tool
            
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> str:
                return func(*args, **kwargs)
            
            return wrapper  # type: ignore
        
        return decorator
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def execute(self, name: str, **kwargs: Any) -> str:
        """Execute a tool by name."""
        tool = self.get(name)
        if tool is None:
            return f"Error: Tool '{name}' not found."
        
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return f"Error executing '{name}': {str(e)}"
    
    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        """Get tools in format suitable for LLM function calling."""
        from llm_client import ToolDefinition
        
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.to_json_schema(),
                function=tool.function,
            )
            for tool in self._tools.values()
        ]
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()


# Global registry instance
registry = ToolRegistry()


# ============================================================================
# Helper function for the decorator shorthand
# ============================================================================

def tool(
    name: str,
    description: str,
    parameters: list[ToolParameter] | None = None,
) -> Callable[[F], F]:
    """
    Shorthand decorator for registering tools.
    
    Usage:
        @tool("ls", "List files in a directory")
        def list_files(path: str = ".") -> str:
            ...
    """
    return registry.register(name, description, parameters)


# ============================================================================
# File System Tools
# ============================================================================

@tool(
    "ls",
    "List files and directories in the specified path. Returns a formatted list of contents.",
    [
        ToolParameter(
            name="path",
            type="string",
            description="The directory path to list. Defaults to current directory.",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="show_hidden",
            type="boolean",
            description="Whether to show hidden files (starting with .)",
            required=False,
            default=False,
        ),
    ],
)
def list_files(path: str = ".", show_hidden: bool = False) -> str:
    """List files in a directory."""
    try:
        config = get_config()
        target_path = Path(path)
        
        # Make relative paths relative to project root
        if not target_path.is_absolute():
            target_path = config.project_root / target_path
        
        if not target_path.exists():
            return f"Error: Path '{path}' does not exist."
        
        if not target_path.is_dir():
            return f"Error: '{path}' is not a directory."
        
        entries = []
        for entry in sorted(target_path.iterdir()):
            # Skip hidden files unless requested
            if not show_hidden and entry.name.startswith("."):
                continue
            
            entry_type = "📁" if entry.is_dir() else "📄"
            size = ""
            if entry.is_file():
                size_bytes = entry.stat().st_size
                if size_bytes < 1024:
                    size = f" ({size_bytes}B)"
                elif size_bytes < 1024 * 1024:
                    size = f" ({size_bytes // 1024}KB)"
                else:
                    size = f" ({size_bytes // (1024 * 1024)}MB)"
            
            entries.append(f"{entry_type} {entry.name}{size}")
        
        if not entries:
            return f"Directory '{path}' is empty."
        
        result = f"Contents of '{target_path}':\n\n"
        result += "\n".join(entries)
        return result
    
    except PermissionError:
        return f"Error: Permission denied to access '{path}'."
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool(
    "read_file",
    "Read the contents of a file. Returns the file content as text.",
    [
        ToolParameter(
            name="filepath",
            type="string",
            description="The path to the file to read.",
            required=True,
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="Starting line number (1-indexed). If not specified, reads from beginning.",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="Ending line number (1-indexed, inclusive). If not specified, reads to end.",
            required=False,
            default=None,
        ),
    ],
)
def read_file(
    filepath: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Read the contents of a file."""
    try:
        config = get_config()
        target_path = Path(filepath)
        
        # Make relative paths relative to project root
        if not target_path.is_absolute():
            target_path = config.project_root / target_path
        
        if not target_path.exists():
            return f"Error: File '{filepath}' does not exist."
        
        if not target_path.is_file():
            return f"Error: '{filepath}' is not a file."
        
        # Read the file
        content = target_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        
        # Apply line range if specified
        if start_line is not None or end_line is not None:
            start_idx = (start_line - 1) if start_line else 0
            end_idx = end_line if end_line else len(lines)
            
            if start_idx < 0:
                start_idx = 0
            if end_idx > len(lines):
                end_idx = len(lines)
            
            lines = lines[start_idx:end_idx]
            
            # Add line numbers
            numbered_lines = []
            for i, line in enumerate(lines, start=start_idx + 1):
                numbered_lines.append(f"{i:4d} | {line.rstrip()}")
            content = "\n".join(numbered_lines)
        
        # Truncate if too long
        max_length = 10000
        if len(content) > max_length:
            content = content[:max_length] + f"\n\n... (truncated, {len(content)} total characters)"
        
        return f"File: {target_path}\n\n{content}"
    
    except UnicodeDecodeError:
        return f"Error: '{filepath}' appears to be a binary file and cannot be read as text."
    except PermissionError:
        return f"Error: Permission denied to read '{filepath}'."
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool(
    "write_file",
    "Create or overwrite a file with the specified content.",
    [
        ToolParameter(
            name="filepath",
            type="string",
            description="The path to the file to create/write.",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="The content to write to the file.",
            required=True,
        ),
        ToolParameter(
            name="create_dirs",
            type="boolean",
            description="Whether to create parent directories if they don't exist.",
            required=False,
            default=True,
        ),
    ],
)
def write_file(
    filepath: str,
    content: str,
    create_dirs: bool = True,
) -> str:
    """Create or overwrite a file with content."""
    try:
        config = get_config()
        target_path = Path(filepath)
        
        # Make relative paths relative to project root
        if not target_path.is_absolute():
            target_path = config.project_root / target_path
        
        # Create parent directories if needed
        if create_dirs:
            target_path.parent.mkdir(parents=True, exist_ok=True)
        elif not target_path.parent.exists():
            return f"Error: Parent directory '{target_path.parent}' does not exist."
        
        # Check if file exists (for messaging)
        file_existed = target_path.exists()
        
        # Write the file
        target_path.write_text(content, encoding="utf-8")
        
        action = "Updated" if file_existed else "Created"
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        
        return f"{action} file: {target_path}\nLines: {line_count}, Size: {len(content)} bytes"
    
    except PermissionError:
        return f"Error: Permission denied to write '{filepath}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool(
    "append_file",
    "Append content to an existing file. Creates the file if it doesn't exist.",
    [
        ToolParameter(
            name="filepath",
            type="string",
            description="The path to the file to append to.",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="The content to append to the file.",
            required=True,
        ),
    ],
)
def append_file(filepath: str, content: str) -> str:
    """Append content to a file."""
    try:
        config = get_config()
        target_path = Path(filepath)
        
        if not target_path.is_absolute():
            target_path = config.project_root / target_path
        
        # Create parent directories if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists
        file_existed = target_path.exists()
        
        # Append to file
        with open(target_path, "a", encoding="utf-8") as f:
            f.write(content)
        
        action = "Appended to" if file_existed else "Created"
        return f"{action} file: {target_path}\nAppended: {len(content)} bytes"
    
    except Exception as e:
        return f"Error appending to file: {str(e)}"


@tool(
    "delete_file",
    "Delete a file from the filesystem.",
    [
        ToolParameter(
            name="filepath",
            type="string",
            description="The path to the file to delete.",
            required=True,
        ),
    ],
)
def delete_file(filepath: str) -> str:
    """Delete a file."""
    try:
        config = get_config()
        target_path = Path(filepath)
        
        if not target_path.is_absolute():
            target_path = config.project_root / target_path
        
        if not target_path.exists():
            return f"Error: File '{filepath}' does not exist."
        
        if not target_path.is_file():
            return f"Error: '{filepath}' is not a file."
        
        target_path.unlink()
        return f"Deleted file: {target_path}"
    
    except PermissionError:
        return f"Error: Permission denied to delete '{filepath}'."
    except Exception as e:
        return f"Error deleting file: {str(e)}"


# ============================================================================
# Shell Command Tool
# ============================================================================

@tool(
    "run_command",
    "Execute a shell command and return the output. Use with caution.",
    [
        ToolParameter(
            name="command",
            type="string",
            description="The shell command to execute.",
            required=True,
        ),
        ToolParameter(
            name="cwd",
            type="string",
            description="Working directory for the command. Defaults to project root.",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Timeout in seconds. Defaults to 30.",
            required=False,
            default=30,
        ),
    ],
)
def run_command(
    command: str,
    cwd: str | None = None,
    timeout: int = 30,
) -> str:
    """Execute a shell command."""
    try:
        config = get_config()
        
        # Set working directory
        working_dir = Path(cwd) if cwd else config.project_root
        if not working_dir.is_absolute():
            working_dir = config.project_root / working_dir
        
        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        output_parts = []
        
        if result.stdout:
            output_parts.append(f"STDOUT:\n{result.stdout}")
        
        if result.stderr:
            output_parts.append(f"STDERR:\n{result.stderr}")
        
        if result.returncode != 0:
            output_parts.append(f"Exit code: {result.returncode}")
        
        if not output_parts:
            return "Command executed successfully (no output)."
        
        return "\n\n".join(output_parts)
    
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"


# ============================================================================
# Web Search Tool
# ============================================================================

@tool(
    "web_search",
    "Search the web for information using DuckDuckGo.",
    [
        ToolParameter(
            name="query",
            type="string",
            description="The search query.",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            type="integer",
            description="Maximum number of results to return. Defaults to 5.",
            required=False,
            default=5,
        ),
    ],
)
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo."""
    if not DDGS_AVAILABLE:
        return (
            "Error: Web search is not available. "
            "Install duckduckgo-search: pip install duckduckgo-search"
        )
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return f"No results found for: {query}"
        
        output = [f"Search results for: {query}\n"]
        
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("href", result.get("link", "No URL"))
            snippet = result.get("body", result.get("snippet", "No description"))
            
            output.append(f"{i}. **{title}**")
            output.append(f"   URL: {url}")
            output.append(f"   {snippet}\n")
        
        return "\n".join(output)
    
    except Exception as e:
        return f"Error searching the web: {str(e)}"


# ============================================================================
# Tavily Search Tool
# ============================================================================

@tool(
    "tavily_search",
    "Search the web using Tavily AI-powered search engine. Returns comprehensive, high-quality search results.",
    [
        ToolParameter(
            name="query",
            type="string",
            description="The search query to find information about.",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            type="integer",
            description="Maximum number of results to return. Defaults to 5.",
            required=False,
            default=5,
        ),
    ],
)
def tavily_search(query: str, max_results: int = 5) -> str:
    """Search the web using Tavily AI-powered search."""
    if not TAVILY_AVAILABLE:
        return (
            "Error: Tavily search is not available. "
            "Install tavily-python: pip install tavily-python"
        )
    
    try:
        config = get_config()
        api_key = config.tavily_api_key
        
        if not api_key:
            return "Error: TAVILY_API_KEY is not set in .env file."
        
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results)
        
        results = response.get("results", [])
        
        if not results:
            return f"No results found for: {query}"
        
        output = [f"Tavily search results for: {query}\n"]
        
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "No URL")
            content = result.get("content", "No description")
            
            output.append(f"{i}. **{title}**")
            output.append(f"   URL: {url}")
            output.append(f"   {content[:300]}...\n" if len(content) > 300 else f"   {content}\n")
        
        return "\n".join(output)
    
    except Exception as e:
        return f"Error searching with Tavily: {str(e)}"


# ============================================================================
# Project Context Tools
# ============================================================================

@tool(
    "get_project_structure",
    "Get the project directory structure as a tree.",
    [
        ToolParameter(
            name="max_depth",
            type="integer",
            description="Maximum depth to traverse. Defaults to 3.",
            required=False,
            default=3,
        ),
        ToolParameter(
            name="include_hidden",
            type="boolean",
            description="Whether to include hidden files and directories.",
            required=False,
            default=False,
        ),
    ],
)
def get_project_structure(max_depth: int = 3, include_hidden: bool = False) -> str:
    """Get the project directory structure."""
    try:
        config = get_config()
        root = config.project_root
        
        # Common directories to skip
        skip_dirs = {
            "__pycache__", "node_modules", ".git", ".venv", "venv",
            "dist", "build", ".cache", ".pytest_cache", "htmlcov",
        }
        
        def build_tree(path: Path, prefix: str = "", depth: int = 0) -> list[str]:
            if depth >= max_depth:
                return []
            
            lines = []
            
            try:
                entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                return [f"{prefix}[Permission denied]"]
            
            # Filter entries
            filtered = []
            for entry in entries:
                if not include_hidden and entry.name.startswith("."):
                    continue
                if entry.is_dir() and entry.name in skip_dirs:
                    continue
                filtered.append(entry)
            
            for i, entry in enumerate(filtered):
                is_last = i == len(filtered) - 1
                connector = "└── " if is_last else "├── "
                
                icon = "📁 " if entry.is_dir() else "📄 "
                lines.append(f"{prefix}{connector}{icon}{entry.name}")
                
                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    lines.extend(build_tree(entry, prefix + extension, depth + 1))
            
            return lines
        
        tree_lines = [f"📂 {root.name}/"]
        tree_lines.extend(build_tree(root))
        
        return "\n".join(tree_lines)
    
    except Exception as e:
        return f"Error building project structure: {str(e)}"


# ============================================================================
# Utility Functions
# ============================================================================

def get_tool_descriptions() -> str:
    """Get a formatted string of all tool descriptions."""
    tools = registry.list_tools()
    lines = ["Available tools:\n"]
    
    for tool in tools:
        lines.append(f"• **{tool.name}**: {tool.description}")
        for param in tool.parameters:
            req = " (required)" if param.required else ""
            lines.append(f"  - `{param.name}` ({param.type}){req}: {param.description}")
        lines.append("")
    
    return "\n".join(lines)


def execute_tool_call(tool_call: dict[str, Any]) -> str:
    """
    Execute a tool call from LLM response.
    
    Args:
        tool_call: Dictionary with 'name' and 'arguments' keys
    
    Returns:
        The tool execution result
    """
    name = tool_call.get("name", "")
    arguments = tool_call.get("arguments", {})
    
    # Handle string arguments (JSON)
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON arguments for tool '{name}'"
    
    return registry.execute(name, **arguments)


# ============================================================================
# Module initialization
# ============================================================================

# Ensure all tools are registered by importing the module
__all__ = [
    "registry",
    "tool",
    "Tool",
    "ToolParameter",
    "ToolRegistry",
    "list_files",
    "read_file",
    "write_file",
    "append_file",
    "delete_file",
    "run_command",
    "web_search",
    "tavily_search",
    "get_project_structure",
    "get_tool_descriptions",
    "execute_tool_call",
]
