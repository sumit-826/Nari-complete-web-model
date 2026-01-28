"""
Klix code - Configuration Management
Handles API keys, model selection, and theme configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ModelProvider(Enum):
    """Available LLM providers."""
    GEMINI = "gemini"
    OLLAMA = "ollama"


class GeminiModel(Enum):
    """Available Gemini models."""
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_2_0_FLASH = "gemini-2.0-flash-exp"


class OllamaModel(Enum):
    """Available Ollama models."""
    DEEPSEEK_OCR = "deepseek-ocr:3b"
    FUNCTIONGEMMA = "functiongemma:270m"
    QWEN3_VL = "qwen3-vl:8b"
    DEEPSEEK_R1 = "deepseek-r1:8b"
    QWEN2_5_CODER = "qwen2.5-coder:3b"
    QWEN2_5_LATEST = "qwen2.5:latest"


@dataclass
class ThemeConfig:
    """TUI Theme configuration."""
    # Primary accent color - Tangerine Orange
    accent_color: str = "#FF8800"
    accent_color_name: str = "orange1"
    
    # Background and text colors
    bg_color: str = "#0D1117"
    text_color: str = "#E6EDF3"
    dim_text_color: str = "#7D8590"
    
    # Border styles
    border_color: str = "#FF8800"
    panel_border_style: str = "double"
    
    # Status colors
    success_color: str = "#3FB950"
    warning_color: str = "#D29922"
    error_color: str = "#F85149"
    info_color: str = "#58A6FF"


@dataclass
class GeminiSafetySettings:
    """
    Safety settings for Gemini API.
    Set to BLOCK_NONE for developer freedom in coding tasks.
    """
    harassment: str = "BLOCK_NONE"
    hate_speech: str = "BLOCK_NONE"
    sexually_explicit: str = "BLOCK_NONE"
    dangerous_content: str = "BLOCK_NONE"
    
    def to_list(self) -> list[dict[str, str]]:
        """Convert to Gemini API format."""
        return [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": self.harassment},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": self.hate_speech},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": self.sexually_explicit},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": self.dangerous_content},
        ]


@dataclass
class Config:
    """Main configuration class for Gemini Code."""
    
    # API Configuration
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    
    # Model Configuration
    default_provider: ModelProvider = field(default=ModelProvider.GEMINI)
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", GeminiModel.GEMINI_2_5_FLASH.value))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", OllamaModel.QWEN2_5_LATEST.value))
    
    # User Information
    user_name: str = field(default_factory=lambda: os.getenv("USER_NAME", "Karan"))
    org_name: str = field(default_factory=lambda: os.getenv("ORG_NAME", "NeuroKaran's Org"))
    
    # Theme
    theme: ThemeConfig = field(default_factory=ThemeConfig)
    
    # Safety Settings
    safety_settings: GeminiSafetySettings = field(default_factory=GeminiSafetySettings)
    
    # Context Management
    max_context_messages: int = 50
    max_tokens_per_message: int = 8000
    sliding_window_size: int = 20
    
    # Project Context
    project_root: Path = field(default_factory=lambda: Path.cwd())
    
    # Memory Configuration (Mem0)
    mem0_api_key: str = field(default_factory=lambda: os.getenv("MEM0_API_KEY", ""))
    memory_enabled: bool = field(default_factory=lambda: os.getenv("MEMORY_ENABLED", "true").lower() == "true")
    
    # Tavily Search Configuration
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    memory_user_id: str = field(default_factory=lambda: os.getenv("USER_NAME", "default"))
    memory_search_limit: int = 10
    memory_auto_extract: bool = True  # Auto-extract memories from conversations
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Parse default model from environment
        default_model = os.getenv("DEFAULT_MODEL", "gemini-2.5-flash")
        if default_model.startswith("gemini"):
            self.default_provider = ModelProvider.GEMINI
            self.gemini_model = default_model
        else:
            self.default_provider = ModelProvider.OLLAMA
            self.ollama_model = default_model
    
    @property
    def current_model(self) -> str:
        """Get the current model name based on provider."""
        if self.default_provider == ModelProvider.GEMINI:
            return self.gemini_model
        return self.ollama_model
    
    @property
    def model_display_name(self) -> str:
        """Get a display-friendly model name."""
        model = self.current_model
        provider = self.default_provider.value.title()
        return f"{provider}: {model}"
    
    def switch_provider(self, provider: ModelProvider | str) -> None:
        """Switch to a different provider."""
        if isinstance(provider, str):
            provider = ModelProvider(provider.lower())
        self.default_provider = provider
    
    def switch_model(self, model: str) -> None:
        """Switch to a different model within the current provider."""
        if self.default_provider == ModelProvider.GEMINI:
            self.gemini_model = model
        else:
            self.ollama_model = model
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        if self.default_provider == ModelProvider.GEMINI and not self.google_api_key:
            issues.append("GOOGLE_API_KEY is not set. Please set it in .env file.")
        
        return issues
    
    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "provider": self.default_provider.value,
            "model": self.current_model,
            "user": self.user_name,
            "org": self.org_name,
            "project_root": str(self.project_root),
        }


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config


def reload_config() -> Config:
    """Reload configuration from environment."""
    global config
    load_dotenv(override=True)
    config = Config()
    return config
