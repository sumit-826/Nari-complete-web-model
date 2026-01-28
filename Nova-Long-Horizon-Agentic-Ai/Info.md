# Klix - Codebase Analysis

This document provides a comprehensive analysis of the Klix codebase, including all major components and their interactions.

## Table of Contents

1. [config.py - Configuration Management](#configpy---configuration-management)
2. [llm_client.py - LLM Client Abstraction Layer](#llm_clientpy---llm-client-abstraction-layer)
3. [main.py - Main Entry Point](#mainpy---main-entry-point)
4. [tools.py - Tools Registry and Implementations](#toolspy---tools-registry-and-implementations)
5. [tui.py - TUI Interface](#tuipy---tui-interface)
6. [mem_0.py - Memory Service](#mem_0py---memory-service)
7. [Architectural Patterns](#architectural-patterns)
8. [Technical Highlights](#technical-highlights)

## config.py - Configuration Management

### Detailed Line-by-Line Analysis

**Lines 1-10: Module Documentation and Imports**
- Line 1-2: Module docstring explaining purpose
- Line 4: Future annotations import for type hints
- Lines 5-10: Standard library imports (os, dataclasses, enum, pathlib, typing)
- Line 12: dotenv import for environment variable loading
- Line 15: Load environment variables from .env file

**Lines 18-41: Enum Definitions**
- Lines 18-21: `ModelProvider` enum with GEMINI and OLLAMA options
- Lines 24-30: `GeminiModel` enum with available Gemini models:
  - GEMINI_2_5_FLASH (default)
  - GEMINI_1_5_PRO
  - GEMINI_1_5_FLASH
  - GEMINI_2_0_FLASH
- Lines 33-39: `OllamaModel` enum with available Ollama models:
  - DEEPSEEK_OCR: 3B parameter model
  - FUNCTIONGEMMA: 270M parameter model
  - QWEN3_VL: 8B parameter vision-language model
  - DEEPSEEK_R1: 8B parameter model
  - QWEN2_5_CODER: 3B parameter coding model (default)

**Lines 44-67: ThemeConfig Dataclass**
- Line 44: Dataclass decorator for ThemeConfig
- Line 45: Class docstring
- Lines 47-48: Primary accent color (Tangerine Orange #FF8800)
- Lines 51-53: Background and text colors for dark theme
- Lines 56-57: Border styling configuration
- Lines 60-64: Status colors for different message types:
  - success_color: Green (#3FB950)
  - warning_color: Yellow (#D29922)
  - error_color: Red (#F85149)
  - info_color: Blue (#58A6FF)

**Lines 70-87: GeminiSafetySettings Dataclass**
- Line 70: Dataclass decorator
- Lines 71-74: Class docstring explaining safety settings
- Lines 76-79: Four safety categories all set to "BLOCK_NONE" by default:
  - harassment
  - hate_speech
  - sexually_explicit
  - dangerous_content
- Lines 82-87: `to_list()` method converts settings to Gemini API format
  - Returns list of dictionaries with category and threshold mappings

**Lines 90-197: Config Dataclass (Main Configuration)**

**Lines 90-110: Field Definitions**
- Line 90: Dataclass decorator for main Config class
- Line 92: Class docstring
- Lines 95-96: API Configuration:
  - google_api_key: Loaded from GOOGLE_API_KEY environment variable
  - ollama_host: Loaded from OLLAMA_HOST, defaults to "http://localhost:11434"
- Lines 99-102: Model Configuration:
  - default_provider: Defaults to ModelProvider.GEMINI
  - gemini_model: Loaded from GEMINI_MODEL env var, defaults to GeminiModel.GEMINI_2_5_FLASH
  - ollama_model: Loaded from OLLAMA_MODEL env var, defaults to OllamaModel.QWEN2_5_CODER
- Lines 105-108: User Information:
  - user_name: Loaded from USER_NAME env var, defaults to "Karan"
  - org_name: Loaded from ORG_NAME env var, defaults to "NeuroKaran's Org"
- Line 111: Theme configuration using ThemeConfig dataclass
- Line 114: Safety settings using GeminiSafetySettings dataclass
- Lines 117-119: Context Management:
  - max_context_messages: 50
  - max_tokens_per_message: 8000
  - sliding_window_size: 20
- Line 122: Project root path defaults to current working directory
- Lines 125-130: Memory Configuration (Mem0 integration):
  - mem0_api_key: Loaded from MEM0_API_KEY env var
  - memory_enabled: Loaded from MEMORY_ENABLED env var, defaults to true
  - memory_user_id: Uses USER_NAME env var, defaults to "default"
  - memory_search_limit: 10
  - memory_auto_extract: True (auto-extract memories from conversations)

**Lines 133-145: Initialization and Validation**
- Lines 133-145: `__post_init__()` method for post-initialization processing:
  - Loads DEFAULT_MODEL from environment
  - Determines provider based on model prefix ("gemini" vs others)
  - Sets appropriate model based on provider detection

**Lines 148-165: Properties and Methods**
- Lines 148-151: `current_model` property returns appropriate model based on provider
- Lines 154-157: `model_display_name` property returns formatted provider:model string
- Lines 160-165: `switch_provider()` method changes active provider (accepts string or enum)
- Lines 168-173: `switch_model()` method changes model within current provider
- Lines 176-186: `validate()` method checks configuration and returns issues list
  - Checks for missing Google API key when using Gemini provider
- Lines 189-197: `to_dict()` method converts config to dictionary for serialization

**Lines 200-208: Global Configuration Management**
- Line 200: Global config instance creation
- Lines 203-205: `get_config()` function returns global instance
- Lines 208-213: `reload_config()` function:
  - Reloads environment variables with override
  - Creates new Config instance
  - Returns updated config

### Key Features
- Environment variable based configuration with sensible defaults
- Type-safe configuration using dataclasses and enums
- Provider-aware model selection
- Comprehensive validation system
- Memory integration configuration
- Theme management for TUI
- Safety settings management for Gemini API

## llm_client.py - LLM Client Abstraction Layer

### Detailed Line-by-Line Analysis

**Lines 1-10: Module Documentation and Imports**
- Lines 1-3: Module docstring explaining purpose
- Line 5: Future annotations import for type hints
- Lines 6-11: Standard library imports (asyncio, abc, dataclasses, typing)
- Lines 13-14: Google GenAI SDK imports
- Line 15: Ollama client import
- Line 17: Config imports for configuration management

**Lines 20-66: Data Classes**

**Lines 20-27: Message Dataclass**
- Line 20: Dataclass decorator for Message
- Line 21: Class docstring
- Line 23: role field (user, assistant, system, tool)
- Line 24: content field for message text
- Line 25: tool_calls field with default empty list
- Line 26: tool_call_id field (optional)
- Line 27: name field for tool responses (optional)

**Lines 30-46: ToolDefinition Dataclass**
- Line 30: Dataclass decorator for ToolDefinition
- Line 31: Class docstring
- Line 33: name field for tool name
- Line 34: description field for tool description
- Line 35: parameters field for tool parameters schema
- Line 36: function field for callable function (optional)
- Lines 38-43: `to_gemini_format()` method converts to Gemini format
- Lines 45-54: `to_ollama_format()` method converts to Ollama format

**Lines 57-66: LLMResponse Dataclass**
- Line 57: Dataclass decorator for LLMResponse
- Line 58: Class docstring
- Line 60: content field for response text
- Line 61: tool_calls field with default empty list
- Line 62: finish_reason field (default "stop")
- Line 63: usage field for token usage statistics
- Line 64: raw_response field for original API response

**Lines 69-118: LLMClient Abstract Base Class**

**Lines 69-76: Class Definition and Constructor**
- Line 69: Abstract base class definition
- Line 70: Class docstring
- Lines 72-76: Constructor with config parameter and system instruction initialization

**Lines 78-84: Abstract Methods**
- Lines 78-84: `chat()` abstract method for chat completion
- Lines 86-88: `generate()` abstract method for text generation

**Lines 90-108: System Instruction Management**
- Lines 90-92: `set_system_instruction()` method
- Lines 94-96: `system_instruction` property getter
- Lines 98-118: `_default_system_instruction()` method with comprehensive role definition for Klix AI assistant

**Lines 121-270: GeminiClient Implementation**

**Lines 121-145: Constructor and Configuration**
- Lines 121-123: Class definition and docstring
- Lines 125-127: Constructor calling parent constructor
- Lines 129-131: Gemini client initialization with API key
- Lines 133-145: Safety settings configuration with all categories set to "OFF"

**Lines 147-180: Message Conversion**
- Lines 147-149: `_convert_messages_to_gemini()` method docstring
- Lines 151-179: Message conversion logic:
  - Skips system messages (handled via system_instruction)
  - Converts user/assistant roles
  - Handles tool calls with function call parts
  - Handles tool responses with function response parts
  - Converts regular text messages

**Lines 182-190: Tool Configuration**
- Lines 182-184: `_create_tools_config()` method docstring
- Lines 186-190: Converts ToolDefinition list to Gemini Tool format

**Lines 192-230: Chat Method**
- Lines 192-198: `chat()` method signature
- Lines 200-202: Message and tool conversion
- Lines 204-210: Generation config with system instruction and safety settings
- Lines 212-214: Streaming response handling
- Lines 216-222: Non-streaming response with async thread execution
- Line 224: Response parsing

**Lines 232-245: Streaming Response**
- Lines 232-235: `_stream_response()` method signature
- Lines 237-241: Stream generation with async thread execution
- Lines 243-244: Yield text chunks from stream

**Lines 247-270: Response Parsing**
- Lines 247-249: `_parse_response()` method signature
- Lines 251-270: Response parsing logic:
  - Extracts text content from response parts
  - Extracts tool calls from function call parts
  - Extracts token usage metadata
  - Returns standardized LLMResponse

**Lines 272-285: Generate Method**
- Lines 272-274: `generate()` method signature
- Lines 276-283: Simple text generation with system instruction
- Line 285: Returns generated text

**Lines 288-380: OllamaClient Implementation**

**Lines 288-295: Constructor**
- Lines 288-290: Class definition and docstring
- Lines 292-295: Constructor with Ollama client initialization

**Lines 297-320: Message Conversion**
- Lines 297-299: `_convert_messages_to_ollama()` method docstring
- Lines 301-320: Message conversion logic:
  - Adds system message if set
  - Converts message roles and content
  - Handles tool calls and tool responses
  - Preserves tool_call_id

**Lines 322-350: Chat Method**
- Lines 322-328: `chat()` method signature
- Lines 330-332: Message and tool conversion
- Lines 334-336: Streaming response handling
- Lines 338-346: Non-streaming response with async thread execution
- Line 348: Response parsing

**Lines 352-365: Streaming Response**
- Lines 352-355: `_stream_response()` method signature
- Lines 357-361: Stream generation with async thread execution
- Lines 363-364: Yield text chunks from stream

**Lines 367-380: Response Parsing**
- Lines 367-369: `_parse_response()` method signature
- Lines 371-380: Response parsing logic:
  - Extracts message content
  - Extracts tool calls from response
  - Calculates token usage
  - Returns standardized LLMResponse

**Lines 382-393: Generate Method**
- Lines 382-384: `generate()` method signature
- Lines 386-391: Simple text generation with system instruction
- Line 393: Returns generated text

**Lines 396-443: Factory Functions**

**Lines 396-415: get_client() Factory**
- Lines 396-405: Function docstring
- Lines 407-408: Config handling with fallback to global config
- Lines 410-413: Provider handling with string conversion
- Lines 415-418: Returns appropriate client based on provider

**Lines 421-425: get_gemini_client()**
- Lines 421-423: Function docstring
- Lines 425-426: Returns Gemini client instance

**Lines 429-433: get_ollama_client()**
- Lines 429-431: Function docstring
- Lines 433-434: Returns Ollama client instance

### Key Features
- Abstract base class pattern for LLM client implementations
- Adapter pattern for different LLM providers (Gemini, Ollama)
- Standardized message and response formats
- Tool/function calling support
- Streaming and non-streaming response handling
- Async/await pattern for non-blocking operations
- Comprehensive error handling and validation
- Factory pattern for client instantiation
- Token usage tracking and reporting

## main.py - Main Entry Point

### Detailed Line-by-Line Analysis

**Lines 1-10: Module Documentation and Imports**
- Lines 1-3: Module docstring explaining purpose
- Line 5: Future annotations import for type hints
- Lines 6-11: Standard library imports (asyncio, sys, dataclasses, datetime, typing)
- Line 13: Typer import for CLI
- Lines 15-19: Local module imports (config, llm_client, mem_0, tools, tui)

**Lines 22-80: MemoryManager Class**

**Lines 22-32: Class Definition and Fields**
- Lines 22-26: Class definition and docstring
- Line 28: messages field with default empty list
- Line 29: max_messages field (default 50)
- Line 30: sliding_window_size field (default 20)
- Line 31: total_tokens_used field (default 0)

**Lines 34-45: Message Management**
- Lines 34-37: `add_message()` method adds message and applies sliding window if needed
- Lines 39-45: `_apply_sliding_window()` method:
  - Preserves system messages
  - Keeps last N non-system messages
  - Reconstructs message list

**Lines 47-58: Context Management**
- Lines 47-49: `get_messages()` method returns copy of messages
- Lines 51-55: `clear()` method clears all messages except system
- Lines 57-61: `get_context_summary()` method returns formatted context info
- Lines 63-66: `update_token_usage()` method updates total token count

**Lines 83-280: SlashCommandHandler Class**

**Lines 83-88: SlashCommand Dataclass**
- Lines 83-86: SlashCommand dataclass with name, description, handler fields

**Lines 91-102: Class Definition and Constructor**
- Lines 91-93: Class definition and docstring
- Lines 95-99: Constructor with agent_loop parameter and command initialization

**Lines 104-118: Command Registration**
- Lines 104-118: `_register_default_commands()` method registers 13 default commands:
  - init, config, clear, help, tools, model, status, memory, forget, remember, quit, exit

**Lines 120-128: Command Management**
- Lines 120-128: `register()` method adds new slash commands
- Lines 130-132: `is_command()` method checks if text starts with "/"

**Lines 134-152: Command Execution**
- Lines 134-142: `execute()` method:
  - Parses command name and arguments
  - Validates command existence
  - Executes command handler
  - Returns True if command was handled

**Lines 155-280: Command Implementations**

**Lines 155-180: _cmd_init()**
- Lines 155-157: Method docstring
- Lines 159-179: Project initialization:
  - Validates project path
  - Sets project root in config
  - Gets project structure
  - Adds system message with project context

**Lines 182-210: _cmd_config()**
- Lines 182-184: Method docstring
- Lines 186-210: Configuration management:
  - Shows current config if no args
  - Parses key=value format
  - Handles model and provider switching

**Lines 212-220: _cmd_clear()**
- Lines 212-214: Method docstring
- Lines 216-220: Clears conversation context and UI

**Lines 222-232: _cmd_help()**
- Lines 222-224: Method docstring
- Lines 226-232: Shows available commands with descriptions

**Lines 234-240: _cmd_tools()**
- Lines 234-236: Method docstring
- Lines 238-240: Shows available tools

**Lines 242-268: _cmd_model()**
- Lines 242-244: Method docstring
- Lines 246-268: Model switching:
  - Shows current model if no args
  - Handles provider switching (gemini/ollama)
  - Handles specific model selection

**Lines 270-284: _cmd_status()**
- Lines 270-272: Method docstring
- Lines 274-284: Shows current status including model, context, memory, project

**Lines 286-310: _cmd_memory()**
- Lines 286-288: Method docstring
- Lines 290-310: Memory management:
  - Shows error if memory disabled
  - Handles search and list modes
  - Displays formatted memory list

**Lines 312-340: _cmd_forget()**
- Lines 312-314: Method docstring
- Lines 316-340: Memory deletion:
  - Handles specific memory deletion
  - Handles "all" deletion with confirmation
  - Shows success/error messages

**Lines 342-360: _cmd_remember()**
- Lines 342-344: Method docstring
- Lines 346-360: Manual memory addition:
  - Validates input
  - Adds semantic memory
  - Shows success/error messages

**Lines 362-368: _cmd_quit()**
- Lines 362-364: Method docstring
- Lines 366-368: Exits application with goodbye message

**Lines 371-590: AgentLoop Class**

**Lines 371-390: Class Definition and Constructor**
- Lines 371-375: Class definition and docstring
- Lines 377-400: Constructor:
  - Initializes config with fallback to global config
  - Handles local mode override
  - Initializes TUI, memory, client, commands
  - Initializes memory service
  - Sets up state variables
  - Initializes system message

**Lines 402-420: System Message Initialization**
- Lines 402-404: `_initialize_system_message()` method docstring
- Lines 406-420: System message setup:
  - Gets memory context if enabled
  - Builds system instruction with memories
  - Adds system message to memory

**Lines 422-450: Tool Call Processing**
- Lines 422-430: `_process_tool_calls()` method docstring
- Lines 432-450: Tool call handling:
  - Shows tool calls in TUI
  - Executes tools
  - Shows results
  - Creates tool response messages
  - Tracks activity

**Lines 452-540: Chat Processing**
- Lines 452-454: `_chat()` method docstring
- Lines 456-540: Main chat processing:
  - Adds user message
  - Gets available tools
  - Shows thinking indicator
  - Gets LLM response
  - Handles tool calls and follow-up responses
  - Updates token usage
  - Handles memory extraction

**Lines 542-620: Main Run Loop**
- Lines 542-544: `run()` method docstring
- Lines 546-620: Main loop:
  - Clears screen and shows header
  - Validates configuration
  - Processes user input
  - Handles slash commands
  - Processes chat messages
  - Handles keyboard interrupts

**Lines 623-690: CLI Entry Point**

**Lines 623-630: Typer App Setup**
- Lines 623-630: Typer app configuration with name, help text

**Lines 632-660: main() Command**
- Lines 632-634: Command definition
- Lines 636-658: CLI options:
  - --local/-l: Use local Ollama model
  - --model/-m: Specify model
  - --project/-p: Project directory
- Lines 660-670: Main function logic:
  - Loads config
  - Applies CLI options
  - Creates and runs AgentLoop

**Lines 672-680: Entry Point**
- Lines 672-680: Typer app execution

### Key Features
- Memory management with sliding window approach
- Comprehensive slash command system
- Main agent loop for conversation management
- Tool call processing and execution
- Token usage tracking
- Memory integration with auto-extraction
- CLI interface with multiple options
- Error handling and user feedback
- Async/await pattern for non-blocking operations

## tools.py - Tools Registry and Implementations

### Detailed Line-by-Line Analysis

**Lines 1-10: Module Documentation and Imports**
- Lines 1-3: Module docstring explaining purpose
- Line 5: Future annotations import for type hints
- Lines 6-11: Standard library imports (json, os, subprocess, dataclasses, functools, pathlib, typing)
- Lines 13-18: DuckDuckGo search import with fallback handling
- Line 20: Config import for configuration access

**Lines 23-30: Type Variable and Tool Parameter Dataclass**
- Line 23: Type variable F for tool functions
- Lines 25-30: `ToolParameter` dataclass:
  - name: Parameter name
  - type: Parameter type
  - description: Parameter description
  - required: Whether parameter is required (default True)
  - default: Default value (optional)

**Lines 33-54: Tool Dataclass**
- Lines 33-36: `Tool` dataclass definition
- Line 37: name field
- Line 38: description field
- Line 39: function field (callable)
- Line 40: parameters field with default empty list
- Lines 42-54: `to_json_schema()` method converts to JSON Schema format
- Lines 56-58: `execute()` method executes tool with arguments

**Lines 61-100: ToolRegistry Singleton Class**

**Lines 61-70: Singleton Implementation**
- Lines 61-63: Class definition and docstring
- Line 65: Singleton instance variable
- Lines 67-70: `__new__()` method implements singleton pattern
- Lines 72-74: `__init__()` method with tools initialization

**Lines 76-94: Tool Registration**
- Lines 76-84: `register()` method decorator
- Lines 86-94: Decorator implementation:
  - Creates Tool instance
  - Registers tool in _tools dictionary
  - Returns wrapped function

**Lines 96-110: Tool Management**
- Lines 96-98: `get()` method retrieves tool by name
- Lines 100-106: `execute()` method executes tool by name with error handling
- Lines 108-110: `list_tools()` method returns all registered tools

**Lines 112-120: LLM Integration**
- Lines 112-120: `get_tools_for_llm()` method:
  - Converts tools to LLM function calling format
  - Uses ToolDefinition from llm_client

**Lines 122-124: Clear Method**
- Lines 122-124: `clear()` method clears all registered tools

**Lines 127-130: Global Registry Instance**
- Lines 127-130: Global registry instance creation

**Lines 133-148: Tool Decorator Shorthand**
- Lines 133-148: `tool()` decorator function:
  - Shorthand for registry.register()
  - Simplified syntax for tool registration

**Lines 151-220: File System Tools**

**Lines 151-190: list_files() Tool**
- Lines 151-168: Tool decorator with parameters:
  - path: Directory path (default ".")
  - show_hidden: Show hidden files (default False)
- Lines 170-190: Implementation:
  - Handles relative/absolute paths
  - Validates directory existence
  - Lists files with icons and sizes
  - Handles permissions and errors

**Lines 193-250: read_file() Tool**
- Lines 193-210: Tool decorator with parameters:
  - filepath: File path (required)
  - start_line: Starting line (optional)
  - end_line: Ending line (optional)
- Lines 212-250: Implementation:
  - Handles relative/absolute paths
  - Validates file existence
  - Supports line range selection
  - Handles binary files and permissions
  - Truncates long content

**Lines 253-290: write_file() Tool**
- Lines 253-270: Tool decorator with parameters:
  - filepath: File path (required)
  - content: Content to write (required)
  - create_dirs: Create parent directories (default True)
- Lines 272-290: Implementation:
  - Handles relative/absolute paths
  - Creates parent directories if needed
  - Writes content with UTF-8 encoding
  - Returns creation/update status

**Lines 293-320: append_file() Tool**
- Lines 293-304: Tool decorator with parameters:
  - filepath: File path (required)
  - content: Content to append (required)
- Lines 306-320: Implementation:
  - Handles relative/absolute paths
  - Creates parent directories if needed
  - Appends content to file
  - Returns append status

**Lines 323-350: delete_file() Tool**
- Lines 323-332: Tool decorator with parameters:
  - filepath: File path (required)
- Lines 334-350: Implementation:
  - Handles relative/absolute paths
  - Validates file existence
  - Deletes file with error handling

**Lines 353-400: run_command() Tool**
- Lines 353-372: Tool decorator with parameters:
  - command: Shell command (required)
  - cwd: Working directory (optional)
  - timeout: Timeout in seconds (default 30)
- Lines 374-400: Implementation:
  - Handles working directory
  - Executes command with subprocess
  - Captures stdout, stderr, and exit code
  - Handles timeouts and errors

**Lines 403-450: web_search() Tool**
- Lines 403-422: Tool decorator with parameters:
  - query: Search query (required)
  - max_results: Maximum results (default 5)
- Lines 424-450: Implementation:
  - Checks DuckDuckGo availability
  - Performs web search
  - Formats results with titles, URLs, and snippets
  - Handles errors

**Lines 453-520: get_project_structure() Tool**
- Lines 453-472: Tool decorator with parameters:
  - max_depth: Maximum depth (default 3)
  - include_hidden: Include hidden files (default False)
- Lines 474-520: Implementation:
  - Recursive tree building function
  - Skips common directories (.git, node_modules, etc.)
  - Formats tree with icons and indentation
  - Handles permissions and errors

**Lines 523-560: Utility Functions**

**Lines 523-540: get_tool_descriptions()**
- Lines 523-525: Function docstring
- Lines 527-540: Formats tool descriptions:
  - Lists all tools with names and descriptions
  - Shows parameters with types and requirements

**Lines 543-560: execute_tool_call()**
- Lines 543-550: Function docstring
- Lines 552-560: Executes tool calls:
  - Extracts tool name and arguments
  - Handles JSON argument parsing
  - Executes tool via registry

**Lines 563-590: Module Initialization**
- Lines 563-588: `__all__` list exports all public functions and classes

### Key Features
- Decorator-based tool registration system
- Singleton pattern for global tool management
- Comprehensive file system operations
- Shell command execution with safety
- Web search integration
- Project structure visualization
- JSON schema conversion for LLM function calling
- Error handling and user-friendly messages
- Type hints and documentation throughout

## tui.py - TUI Interface

### Detailed Line-by-Line Analysis

**Lines 1-10: Module Documentation and Imports**
- Lines 1-3: Module docstring explaining purpose
- Line 5: Future annotations import for type hints
- Lines 6-11: Standard library imports (asyncio, os, dataclasses, datetime, pathlib, typing)
- Lines 13-24: Rich library imports for TUI components
- Line 26: Config import for configuration access

**Lines 28-34: ASCII Art**
- Lines 28-34: ROBOT_ASCII constant with simple rectangle design

**Lines 37-62: Data Classes**

**Lines 37-44: RecentActivity Dataclass**
- Lines 37-39: Class definition and docstring
- Line 41: timestamp field
- Line 42: action field
- Line 43: details field with default empty string

**Lines 47-62: TUIState Dataclass**
- Lines 47-49: Class definition and docstring
- Line 51: recent_activities field with default empty list
- Line 52: is_thinking field (default False)
- Line 53: current_model field with default empty string
- Line 54: token_usage field with default empty dict
- Lines 56-62: `add_activity()` method adds activity and limits to 5 items

**Lines 65-479: GeminiCodeTUI Class**

**Lines 65-75: Class Definition and Constructor**
- Lines 65-69: Class definition and docstring
- Line 71: VERSION constant
- Lines 73-79: Constructor:
  - Initializes config with fallback
  - Creates console with truecolor support
  - Initializes state
  - Sets up styles

**Lines 81-90: Style Setup**
- Lines 81-83: `_setup_styles()` method docstring
- Lines 85-90: Sets up custom styles based on theme configuration

**Lines 92-160: Header Rendering**
- Lines 92-95: `render_header()` method docstring
- Lines 97-160: Complex header rendering:
  - Creates two-column table layout
  - Left column: welcome text, ASCII art, model info, org, path
  - Right column: tips, recent activity
  - Returns styled panel with rounded border

**Lines 162-180: Input Prompt**
- Lines 162-165: `render_input_prompt()` method docstring
- Lines 167-180: Input prompt rendering:
  - Creates styled prompt text
  - Uses Rich Prompt.ask for user input
  - Handles keyboard interrupts

**Lines 182-195: Footer Rendering**
- Lines 182-184: `render_footer()` method docstring
- Lines 186-195: Footer rendering:
  - Creates two-column table
  - Left: shortcuts hint
  - Right: notice message

**Lines 197-210: Thinking Spinner**
- Lines 197-199: `render_thinking_spinner()` method docstring
- Lines 201-210: Creates progress spinner with dots animation

**Lines 212-225: Thinking Indicator**
- Lines 212-214: `show_thinking()` method docstring
- Lines 216-225: Async thinking indicator:
  - Sets thinking state
  - Shows spinner until state changes

**Lines 227-230: Stop Thinking**
- Lines 227-230: `stop_thinking()` method clears thinking state

**Lines 232-260: Message Rendering**
- Lines 232-237: `render_message()` method docstring
- Lines 239-260: Message rendering:
  - Determines styling based on role (user, assistant, tool, system)
  - Parses Markdown content
  - Creates styled panel with appropriate icon

**Lines 262-280: Code Rendering**
- Lines 262-265: `render_code()` method docstring
- Lines 267-280: Code rendering:
  - Uses Syntax with Monokai theme
  - Adds line numbers and word wrap
  - Creates styled panel

**Lines 282-305: Tool Call Rendering**
- Lines 282-286: `render_tool_call()` method docstring
- Lines 288-305: Tool call rendering:
  - Shows tool name and arguments
  - Displays result in styled panel if available

**Lines 307-320: Error Rendering**
- Lines 307-309: `render_error()` method docstring
- Lines 311-320: Error message rendering:
  - Creates red error panel with cross icon

**Lines 322-335: Success Rendering**
- Lines 322-324: `render_success()` method docstring
- Lines 326-335: Success message rendering:
  - Creates green success panel with check icon

**Lines 337-350: Info Rendering**
- Lines 337-339: `render_info()` method docstring
- Lines 341-350: Info message rendering:
  - Creates blue info panel with info icon

**Lines 352-358: Clear Method**
- Lines 352-354: `clear()` method docstring
- Lines 356-358: Clears console

**Lines 360-366: Print Method**
- Lines 360-362: `print()` method docstring
- Lines 364-366: Proxy to console.print

**Lines 368-385: Stream Response**
- Lines 368-370: `stream_response()` method docstring
- Lines 372-385: Streaming response handling:
  - Uses Live display for real-time updates
  - Accumulates chunks and updates display
  - Returns full content

**Lines 387-396: Factory Function**
- Lines 387-390: `create_tui()` function docstring
- Lines 392-396: Creates and returns TUI instance

**Lines 399-430: Standalone Demo**
- Lines 399-401: Main guard for standalone execution
- Lines 403-430: Demo code showing:
  - Header rendering
  - Input prompt placeholder
  - Footer rendering

### Key Features
- Rich library-based sophisticated TUI
- Themed styling with accent colors
- Markdown support for messages
- Syntax highlighting for code
- Thinking indicators with spinners
- Activity tracking and display
- Error, success, and info message panels
- Responsive layout with tables and panels
- Streaming response display
- Comprehensive styling system

## Key Architectural Patterns

1. **Adapter Pattern**: LLMClient abstract base class with GeminiClient and OllamaClient implementations
2. **Singleton Pattern**: ToolRegistry for global tool management
3. **Decorator Pattern**: @tool decorator for tool registration
4. **Factory Pattern**: get_client() for client instantiation
5. **State Management**: MemoryManager for conversation context
6. **Command Pattern**: SlashCommandHandler for slash commands

## Technical Highlights

- **Async/Await**: Extensive use of asyncio for non-blocking operations
- **Type Hints**: Comprehensive type annotations throughout
- **Error Handling**: Robust error handling with user-friendly messages
- **Configuration**: Environment-based configuration with validation
- **Tool Integration**: Seamless integration of file operations and web search
- **UI/UX**: Rich library for sophisticated terminal interface

The codebase demonstrates modern Python practices with clean architecture, proper separation of concerns, and comprehensive documentation.