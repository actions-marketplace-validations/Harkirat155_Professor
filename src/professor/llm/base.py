"""LLM provider abstraction and integration."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from enum import Enum
import structlog

logger = structlog.get_logger()


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class LLMMessage(ABC):
    """Base class for LLM messages."""

    def __init__(self, role: str, content: str) -> None:
        """Initialize message.

        Args:
            role: Message role (system, user, assistant)
            content: Message content
        """
        self.role = role
        self.content = content


class LLMResponse(ABC):
    """Base class for LLM responses."""

    def __init__(
        self,
        content: str,
        model: str,
        tokens_used: int,
        cost: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize response.

        Args:
            content: Response content
            model: Model name used
            tokens_used: Total tokens consumed
            cost: Estimated cost in USD
            metadata: Additional metadata
        """
        self.content = content
        self.model = model
        self.tokens_used = tokens_used
        self.cost = cost
        self.metadata = metadata or {}


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        """Initialize LLM client.

        Args:
            api_key: API key for the provider
            model: Model name to use
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific parameters
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_params = kwargs
        self.total_tokens_used = 0
        self.total_cost = 0.0

    @abstractmethod
    async def complete(
        self, messages: list[LLMMessage], **kwargs: Any
    ) -> LLMResponse:
        """Generate completion from messages.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters for this request

        Returns:
            LLM response with generated content

        Raises:
            LLMError: If completion fails
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        pass

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        pass

    def get_stats(self) -> dict[str, Any]:
        """Get usage statistics.

        Returns:
            Dictionary with usage stats
        """
        return {
            "total_tokens_used": self.total_tokens_used,
            "total_cost": self.total_cost,
            "model": self.model,
        }

    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self.total_tokens_used = 0
        self.total_cost = 0.0


class LLMError(Exception):
    """Base exception for LLM errors."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""

    pass


class LLMAPIError(LLMError):
    """Raised when LLM API returns an error."""

    pass


class LLMInvalidResponseError(LLMError):
    """Raised when LLM returns invalid response."""

    pass
