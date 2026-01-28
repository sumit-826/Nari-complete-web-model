"""
Klix - Main Entry Point
Async event loop with AgentLoop, MemoryManager, and slash commands.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import typer

from config import Config, ModelProvider, get_config, reload_config
from llm_client import LLMClient, LLMResponse, Message, get_client
from mem_0 import MemoryService, get_memory_service
from tools import execute_tool_call, get_tool_descriptions, registry
from tui import GeminiCodeTUI, create_tui


# ============================================================================
# Memory Manager
# ============================================================================

@dataclass
class MemoryManager:
    """
    Manages conversation context with a sliding window approach.
    Keeps prompts efficient while maintaining conversation coherence.
    """
    
    messages: list[Message] = field(default_factory=list)
    max_messages: int = 50
    sliding_window_size: int = 20
    total_tokens_used: int = 0
    
    def add_message(self, message: Message) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)
        
        # Apply sliding window if we exceed max
        if len(self.messages) > self.max_messages:
            self._apply_sliding_window()
    
    def _apply_sliding_window(self) -> None:
        """
        Apply sliding window to keep conversation manageable.
        Keeps system message + last N messages.
        """
        # Find system messages to preserve
        system_messages = [m for m in self.messages if m.role == "system"]
        
        # Keep last N non-system messages
        non_system = [m for m in self.messages if m.role != "system"]
        recent = non_system[-self.sliding_window_size:]
        
        # Reconstruct messages
        self.messages = system_messages + recent
    
    def get_messages(self) -> list[Message]:
        """Get all messages in the conversation."""
        return self.messages.copy()
    
    def clear(self) -> None:
        """Clear all messages except system."""
        system_messages = [m for m in self.messages if m.role == "system"]
        self.messages = system_messages
        self.total_tokens_used = 0
    
    def get_context_summary(self) -> str:
        """Get a summary of the current context."""
        return (
            f"Messages: {len(self.messages)}, "
            f"Tokens used: {self.total_tokens_used:,}"
        )
    
    def update_token_usage(self, usage: dict[str, int]) -> None:
        """Update total token usage."""
        self.total_tokens_used += usage.get("total_tokens", 0)


# ============================================================================
# Slash Command Handler
# ============================================================================

@dataclass
class SlashCommand:
    """Represents a slash command."""
    name: str
    description: str
    handler: Any  # Callable


class SlashCommandHandler:
    """Handles slash commands for the CLI."""
    
    def __init__(self, agent_loop: AgentLoop) -> None:
        self.agent = agent_loop
        self._commands: dict[str, SlashCommand] = {}
        self._register_default_commands()
    
    def _register_default_commands(self) -> None:
        """Register the default slash commands."""
        self.register("init", "Initialize project context", self._cmd_init)
        self.register("config", "View or change configuration", self._cmd_config)
        self.register("clear", "Clear conversation context", self._cmd_clear)
        self.register("help", "Show available commands", self._cmd_help)
        self.register("tools", "Show available tools", self._cmd_tools)
        self.register("model", "Switch model (gemini/ollama)", self._cmd_model)
        self.register("status", "Show current status", self._cmd_status)
        self.register("memory", "View and search memories", self._cmd_memory)
        self.register("forget", "Delete a memory", self._cmd_forget)
        self.register("remember", "Manually add a memory", self._cmd_remember)
        self.register("quit", "Exit Klix", self._cmd_quit)
        self.register("exit", "Exit Klix", self._cmd_quit)
    
    def register(
        self,
        name: str,
        description: str,
        handler: Any,
    ) -> None:
        """Register a new slash command."""
        self._commands[name] = SlashCommand(name, description, handler)
    
    def is_command(self, text: str) -> bool:
        """Check if text is a slash command."""
        return text.strip().startswith("/")
    
    async def execute(self, text: str) -> bool:
        """
        Execute a slash command.
        
        Returns:
            True if command was handled, False otherwise
        """
        if not self.is_command(text):
            return False
        
        parts = text.strip()[1:].split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd_name not in self._commands:
            self.agent.tui.render_error(
                f"Unknown command: /{cmd_name}\nUse /help to see available commands."
            )
            return True
        
        command = self._commands[cmd_name]
        await command.handler(args)
        return True
    
    # ========================================================================
    # Command Implementations
    # ========================================================================
    
    async def _cmd_init(self, args: str) -> None:
        """Initialize project context."""
        from pathlib import Path
        
        project_path = Path(args.strip()) if args.strip() else Path.cwd()
        
        if not project_path.exists():
            self.agent.tui.render_error(f"Path does not exist: {project_path}")
            return
        
        self.agent.config.project_root = project_path.resolve()
        
        # Build project context
        from tools import get_project_structure
        structure = get_project_structure(max_depth=2)
        
        # Add to system context
        context_message = Message(
            role="system",
            content=f"""Project initialized at: {project_path.resolve()}

Project structure:
{structure}

Remember this context when answering questions about the project.""",
        )
        self.agent.memory.add_message(context_message)
        
        self.agent.tui.render_success(
            f"Initialized project context at: {project_path.resolve()}",
            title="Project Initialized",
        )
        self.agent.tui.state.add_activity("Initialized project", str(project_path))
    
    async def _cmd_config(self, args: str) -> None:
        """Show or update configuration."""
        config = self.agent.config
        
        if not args:
            # Show current config
            info = [
                f"**Provider:** {config.default_provider.value}",
                f"**Model:** {config.current_model}",
                f"**User:** {config.user_name}",
                f"**Org:** {config.org_name}",
                f"**Project Root:** {config.project_root}",
            ]
            self.agent.tui.render_info("\n".join(info), title="Configuration")
        else:
            # Parse config change
            parts = args.split("=", 1)
            if len(parts) != 2:
                self.agent.tui.render_error("Usage: /config KEY=VALUE")
                return
            
            key, value = parts[0].strip(), parts[1].strip()
            
            if key == "model":
                config.switch_model(value)
                self.agent.client = get_client(config=config)
                self.agent.tui.render_success(f"Switched model to: {value}")
            elif key == "provider":
                try:
                    config.switch_provider(value)
                    self.agent.client = get_client(config=config)
                    self.agent.tui.render_success(f"Switched provider to: {value}")
                except ValueError:
                    self.agent.tui.render_error(f"Invalid provider: {value}")
            else:
                self.agent.tui.render_error(f"Unknown config key: {key}")
    
    async def _cmd_clear(self, args: str) -> None:
        """Clear conversation context."""
        self.agent.memory.clear()
        self.agent.tui.clear()
        self.agent.tui.console.print(self.agent.tui.render_header())
        self.agent.tui.render_success("Conversation context cleared.", title="Context Cleared")
        self.agent.tui.state.add_activity("Cleared context")
    
    async def _cmd_help(self, args: str) -> None:
        """Show help for commands."""
        help_lines = ["**Available Commands:**\n"]
        
        for cmd in sorted(self._commands.values(), key=lambda c: c.name):
            help_lines.append(f"• **/{cmd.name}** - {cmd.description}")
        
        self.agent.tui.render_info("\n".join(help_lines), title="Help")
    
    async def _cmd_tools(self, args: str) -> None:
        """Show available tools."""
        tools_desc = get_tool_descriptions()
        self.agent.tui.render_info(tools_desc, title="Available Tools")
    
    async def _cmd_model(self, args: str) -> None:
        """Switch between models."""
        if not args:
            current = self.agent.config.current_model
            provider = self.agent.config.default_provider.value
            
            info = [
                f"**Current:** {provider} - {current}",
                "",
                "**Usage:**",
                "• `/model gemini` - Switch to Gemini",
                "• `/model ollama` - Switch to Ollama (local)",
                "• `/model gemini-1.5-flash` - Use specific model",
            ]
            self.agent.tui.render_info("\n".join(info), title="Model Selection")
            return
        
        model = args.strip().lower()
        
        # Check if it's a provider switch
        if model in ("gemini", "ollama"):
            self.agent.config.switch_provider(model)
            self.agent.client = get_client(config=self.agent.config)
            self.agent.tui.render_success(
                f"Switched to {model.title()} ({self.agent.config.current_model})"
            )
        else:
            # Assume it's a specific model name
            if model.startswith("gemini"):
                self.agent.config.switch_provider("gemini")
            self.agent.config.switch_model(model)
            self.agent.client = get_client(config=self.agent.config)
            self.agent.tui.render_success(f"Switched to model: {model}")
        
        self.agent.tui.state.add_activity("Switched model", model)
    
    async def _cmd_status(self, args: str) -> None:
        """Show current status."""
        context = self.agent.memory.get_context_summary()
        config = self.agent.config
        
        # Get memory stats
        memory_status = "Disabled"
        if self.agent.memory_service.is_enabled:
            stats = self.agent.memory_service.get_stats()
            memory_status = f"{stats.get('total_memories', 0)} memories"
        
        info = [
            f"**Model:** {config.current_model}",
            f"**Provider:** {config.default_provider.value}",
            f"**Context:** {context}",
            f"**Memory:** {memory_status}",
            f"**Project:** {config.project_root}",
        ]
        self.agent.tui.render_info("\n".join(info), title="Status")
    
    async def _cmd_memory(self, args: str) -> None:
        """View and search memories."""
        if not self.agent.memory_service.is_enabled:
            self.agent.tui.render_error("Memory service is not enabled. Check MEM0_API_KEY in .env")
            return
        
        if args.strip().startswith("search "):
            # Search mode
            query = args.strip()[7:]
            memories = self.agent.memory_service.search(
                query=query,
                user_id=self.agent.config.memory_user_id,
                limit=10,
            )
            title = f"Memory Search: {query}"
        else:
            # List all memories
            memories = self.agent.memory_service.get_all(
                user_id=self.agent.config.memory_user_id,
                limit=20,
            )
            title = "Recent Memories"
        
        if not memories:
            self.agent.tui.render_info("No memories found.", title=title)
            return
        
        lines = []
        for mem in memories:
            type_icon = {
                "episodic": "📅",
                "semantic": "💡",
                "procedural": "⚙️",
            }.get(mem.memory_type.value, "•")
            lines.append(f"{type_icon} `{mem.id[:8]}` {mem.content[:100]}..." if len(mem.content) > 100 else f"{type_icon} `{mem.id[:8]}` {mem.content}")
        
        self.agent.tui.render_info("\n".join(lines), title=title)
    
    async def _cmd_forget(self, args: str) -> None:
        """Delete a memory."""
        if not self.agent.memory_service.is_enabled:
            self.agent.tui.render_error("Memory service is not enabled.")
            return
        
        if not args.strip():
            self.agent.tui.render_error("Usage: /forget <memory_id> or /forget all")
            return
        
        if args.strip().lower() == "all":
            # Confirm deletion
            self.agent.tui.render_info(
                "⚠️ This will delete ALL memories. Type '/forget all confirm' to proceed.",
                title="Confirm Delete All"
            )
            return
        
        if args.strip().lower() == "all confirm":
            success = self.agent.memory_service.delete_all(
                user_id=self.agent.config.memory_user_id
            )
            if success:
                self.agent.tui.render_success("All memories deleted.", title="Memories Cleared")
            else:
                self.agent.tui.render_error("Failed to delete memories.")
            return
        
        # Delete specific memory - support partial ID matching
        partial_id = args.strip().strip("<>")  # Remove any accidental angle brackets
        
        # Find the full ID by matching the prefix
        memories = self.agent.memory_service.get_all(
            user_id=self.agent.config.memory_user_id,
            limit=100,
        )
        
        full_id = None
        for mem in memories:
            if mem.id.startswith(partial_id):
                full_id = mem.id
                break
        
        if not full_id:
            self.agent.tui.render_error(f"No memory found matching ID: {partial_id}")
            return
        
        success = self.agent.memory_service.delete(full_id)
        if success:
            self.agent.tui.render_success(f"Memory {full_id[:8]}... deleted.", title="Memory Deleted")
        else:
            self.agent.tui.render_error(f"Failed to delete memory {partial_id}")
    
    async def _cmd_remember(self, args: str) -> None:
        """Manually add a memory."""
        if not self.agent.memory_service.is_enabled:
            self.agent.tui.render_error("Memory service is not enabled.")
            return
        
        if not args.strip():
            self.agent.tui.render_error("Usage: /remember <text to remember>")
            return
        
        from mem_0 import MemoryType
        success = self.agent.memory_service.add_text(
            text=args.strip(),
            user_id=self.agent.config.memory_user_id,
            memory_type=MemoryType.SEMANTIC,
        )
        
        if success:
            self.agent.tui.render_success(f"Remembered: {args.strip()}", title="Memory Added")
        else:
            self.agent.tui.render_error("Failed to add memory.")
    
    async def _cmd_quit(self, args: str) -> None:
        """Exit the application."""
        self.agent.tui.render_info("Goodbye! 👋", title="Exiting")
        self.agent.running = False


# ============================================================================
# Agent Loop
# ============================================================================

class AgentLoop:
    """
    Main agent loop that manages conversation, tools, and LLM interaction.
    """
    
    def __init__(
        self,
        config: Config | None = None,
        use_local: bool = False,
    ) -> None:
        self.config = config or get_config()
        
        # Override to local if requested
        if use_local:
            self.config.switch_provider(ModelProvider.OLLAMA)
        
        # Initialize components
        self.tui = create_tui(self.config)
        self.memory = MemoryManager(
            max_messages=self.config.max_context_messages,
            sliding_window_size=self.config.sliding_window_size,
        )
        self.client = get_client(config=self.config)
        self.commands = SlashCommandHandler(self)
        
        # Initialize persistent memory service (mem0)
        self.memory_service = get_memory_service(config=self.config)
        
        # State
        self.running = False
        self._thinking_task: asyncio.Task | None = None
        self._last_user_input: str = ""  # Track for memory extraction
        
        # Add system message
        self._initialize_system_message()
    
    def _initialize_system_message(self) -> None:
        """Add the initial system message with memory context."""
        # Get persistent memory context
        memory_context = ""
        if self.memory_service.is_enabled:
            memory_context = self.memory_service.get_memory_context(
                query="user preferences and recent context",
                user_id=self.config.memory_user_id,
                max_memories=self.config.memory_search_limit,
            )
        
        # Build system instruction with memories
        system_content = self.client.system_instruction
        if memory_context:
            system_content += f"\n\n## Your Memories About This User:\n{memory_context}\n\nUse these memories to provide personalized, context-aware assistance."
        
        system_msg = Message(
            role="system",
            content=system_content,
        )
        self.memory.add_message(system_msg)
    
    async def _process_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[Message]:
        """
        Process tool calls from LLM response.
        
        Returns:
            List of tool response messages
        """
        tool_responses = []
        
        for tc in tool_calls:
            tool_name = tc.get("name", "")
            arguments = tc.get("arguments", {})
            tool_id = tc.get("id", f"call_{tool_name}")
            
            # Show tool call in TUI
            self.tui.render_tool_call(tool_name, arguments)
            
            # Execute tool
            result = execute_tool_call(tc)
            
            # Show result
            self.tui.render_tool_call(tool_name, arguments, result)
            
            # Add to responses
            tool_responses.append(Message(
                role="tool",
                content=result,
                tool_call_id=tool_id,
                name=tool_name,
            ))
            
            # Track activity
            self.tui.state.add_activity(f"Used {tool_name}")
        
        return tool_responses
    
    async def _chat(self, user_input: str) -> None:
        """Process a chat message and get response."""
        # Add user message
        user_msg = Message(role="user", content=user_input)
        self.memory.add_message(user_msg)
        
        # Get tools for LLM
        tools = registry.get_tools_for_llm()
        
        # Start thinking indicator
        self.tui.state.is_thinking = True
        thinking_task = asyncio.create_task(
            self.tui.show_thinking("Thinking...")
        )
        
        try:
            # Get response from LLM
            response: LLMResponse = await self.client.chat(
                self.memory.get_messages(),
                tools=tools,
                stream=False,
            )
            
            # Stop thinking
            self.tui.stop_thinking()
            await asyncio.sleep(0.1)  # Let the spinner stop
            
            # Update token usage
            if response.usage:
                self.memory.update_token_usage(response.usage)
                self.tui.state.token_usage = {
                    "total_tokens": self.memory.total_tokens_used
                }
            
            # Handle tool calls
            if response.tool_calls:
                # Add assistant message with tool calls
                assistant_msg = Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
                self.memory.add_message(assistant_msg)
                
                # Process tools
                tool_responses = await self._process_tool_calls(response.tool_calls)
                for tr in tool_responses:
                    self.memory.add_message(tr)
                
                # Get follow-up response after tool use
                self.tui.state.is_thinking = True
                thinking_task = asyncio.create_task(
                    self.tui.show_thinking("Processing results...")
                )
                
                follow_up: LLMResponse = await self.client.chat(
                    self.memory.get_messages(),
                    tools=tools,
                    stream=False,
                )
                
                self.tui.stop_thinking()
                await asyncio.sleep(0.1)
                
                # Render final response
                if follow_up.content:
                    self.tui.render_message(follow_up.content, role="assistant")
                    self.memory.add_message(Message(
                        role="assistant",
                        content=follow_up.content,
                    ))
            else:
                # Regular response without tool calls
                if response.content:
                    self.tui.render_message(response.content, role="assistant")
                    self.memory.add_message(Message(
                        role="assistant",
                        content=response.content,
                    ))
        
        except Exception as e:
            self.tui.stop_thinking()
            self.tui.render_error(str(e), title="Error")
        
        finally:
            self.tui.stop_thinking()
            if thinking_task and not thinking_task.done():
                thinking_task.cancel()
                try:
                    await thinking_task
                except asyncio.CancelledError:
                    pass
            
            # Auto-extract and store memories from the exchange
            if self.config.memory_auto_extract and self.memory_service.is_enabled:
                # Get the last assistant response
                messages = self.memory.get_messages()
                assistant_responses = [m for m in messages if m.role == "assistant"]
                if assistant_responses:
                    last_response = assistant_responses[-1].content
                    self.memory_service.extract_and_store(
                        user_input=user_input,
                        assistant_response=last_response,
                        user_id=self.config.memory_user_id,
                    )
    
    async def run(self) -> None:
        """Main run loop."""
        self.running = True
        
        # Clear screen and show header
        self.tui.clear()
        self.tui.console.print(self.tui.render_header())
        
        # Validate config
        issues = self.config.validate()
        if issues:
            for issue in issues:
                self.tui.render_error(issue, title="Configuration Issue")
        
        # Main loop
        while self.running:
            try:
                # Show footer
                self.tui.render_footer()
                
                # Get user input
                user_input = self.tui.render_input_prompt()
                
                if not user_input:
                    continue
                
                # Check for slash commands
                if await self.commands.execute(user_input):
                    continue
                
                # Show user message
                self.tui.render_message(user_input, role="user")
                
                # Process chat
                await self._chat(user_input)
            
            except KeyboardInterrupt:
                self.tui.print("\n")
                self.tui.render_info("Use /quit to exit or Ctrl+C again to force quit.")
                try:
                    await asyncio.sleep(0.5)
                except KeyboardInterrupt:
                    break
            
            except Exception as e:
                self.tui.render_error(str(e), title="Unexpected Error")
        
        self.tui.print("\nGoodbye! 👋\n")


# ============================================================================
# CLI Entry Point
# ============================================================================

app = typer.Typer(
    name="klix-code",
    help="Klix code - AI-powered coding assistant",
    add_completion=False,
)


@app.command()
def main(
    local: bool = typer.Option(
        False,
        "--local",
        "-l",
        help="Use local Ollama model instead of Gemini",
    ),
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Specify model to use (e.g., gemini-1.5-pro, llama3)",
    ),
    project: str = typer.Option(
        None,
        "--project",
        "-p",
        help="Project directory to initialize",
    ),
) -> None:
    """
    Start Klix code - an AI-powered coding assistant.
    
    Uses Google Gemini by default, or Ollama with --local flag.
    """
    # Load config
    config = get_config()
    
    # Apply CLI options
    if model:
        if model.startswith("gemini"):
            config.switch_provider("gemini")
        else:
            config.switch_provider("ollama")
        config.switch_model(model)
    
    if project:
        from pathlib import Path
        config.project_root = Path(project).resolve()
    
    # Create and run agent
    agent = AgentLoop(config=config, use_local=local)
    
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")
        sys.exit(0)


if __name__ == "__main__":
    app()
