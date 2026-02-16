"""Anthropic LLM client implementation."""

from typing import Any, Optional
import structlog
from anthropic import AsyncAnthropic, APIError, RateLimitError, APITimeoutError

from professor.llm.base import (
    BaseLLMClient,
    LLMMessage,
    LLMResponse,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMAPIError,
)

logger = structlog.get_logger()


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude LLM client."""

    # Pricing per 1M tokens (as of 2024)
    PRICING = {
        "claude-3-5-sonnet-20240620": {"input": 3.0, "output": 15.0},
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20240620",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum response tokens
            **kwargs: Additional parameters
        """
        super().__init__(api_key, model, temperature, max_tokens, **kwargs)
        self.client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self, messages: list[LLMMessage], **kwargs: Any
    ) -> LLMResponse:
        """Generate completion using Claude.

        Args:
            messages: Conversation messages
            **kwargs: Override parameters

        Returns:
            LLM response

        Raises:
            LLMError: If completion fails
        """
        try:
            # Convert messages to Anthropic format
            formatted_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
                if msg.role != "system"
            ]

            # Extract system message if present
            system_message = next(
                (msg.content for msg in messages if msg.role == "system"), None
            )

            # Call API
            response = await self.client.messages.create(
                model=kwargs.get("model", self.model),
                messages=formatted_messages,
                system=system_message,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )

            # Extract response
            content = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens

            # Calculate cost
            cost = self.estimate_cost(input_tokens, output_tokens)

            # Update stats
            self.total_tokens_used += total_tokens
            self.total_cost += cost

            logger.info(
                "anthropic_completion",
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
            )

            return LLMResponse(
                content=content,
                model=self.model,
                tokens_used=total_tokens,
                cost=cost,
                metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "stop_reason": response.stop_reason,
                },
            )

        except RateLimitError as e:
            logger.error("anthropic_rate_limit", error=str(e))
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            logger.error("anthropic_timeout", error=str(e))
            raise LLMTimeoutError(f"Request timed out: {e}") from e
        except APIError as e:
            logger.error("anthropic_api_error", error=str(e))
            raise LLMAPIError(f"API error: {e}") from e
        except Exception as e:
            logger.error("anthropic_unexpected_error", error=str(e))
            raise LLMError(f"Unexpected error: {e}") from e

    def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's method.

        Args:
            text: Text to count

        Returns:
            Approximate token count
        """
        # Anthropic doesn't have a public tokenizer, use approximation
        # Roughly 4 characters per token for Claude
        return len(text) // 4

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for token usage.

        Args:
            input_tokens: Input tokens
            output_tokens: Output tokens

        Returns:
            Estimated cost in USD
        """
        pricing = self.PRICING.get(self.model)
        if not pricing:
            logger.warning("unknown_model_pricing", model=self.model)
            return 0.0

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
