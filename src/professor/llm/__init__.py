"""LLM module initialization."""

from professor.llm.base import (
    BaseLLMClient,
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMResponse,
)

try:
    from professor.llm.anthropic_client import AnthropicClient
    from professor.llm.openai_client import OpenAIClient

    __all__ = [
        "BaseLLMClient",
        "LLMError",
        "LLMMessage",
        "LLMProvider",
        "LLMResponse",
        "AnthropicClient",
        "OpenAIClient",
    ]
except ImportError:
    # LLM clients are optional for testing
    __all__ = [
        "BaseLLMClient",
        "LLMError",
        "LLMMessage",
        "LLMProvider",
        "LLMResponse",
    ]
