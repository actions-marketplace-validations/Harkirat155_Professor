"""OpenAI LLM client implementation."""

from typing import Any
import structlog
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError
import tiktoken

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


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT LLM client."""

    # Pricing per 1M tokens (as of 2024)
    PRICING = {
        "gpt-4-turbo-preview": {"input": 10.0, "output": 30.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "gpt-3.5-turbo-16k": {"input": 3.0, "output": 4.0},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum response tokens
            **kwargs: Additional parameters
        """
        super().__init__(api_key, model, temperature, max_tokens, **kwargs)
        self.client = AsyncOpenAI(api_key=api_key)

        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning("tokenizer_not_found", model=model)
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    async def complete(
        self, messages: list[LLMMessage], **kwargs: Any
    ) -> LLMResponse:
        """Generate completion using GPT.

        Args:
            messages: Conversation messages
            **kwargs: Override parameters

        Returns:
            LLM response

        Raises:
            LLMError: If completion fails
        """
        try:
            # Convert messages to OpenAI format
            formatted_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            # Call API
            response = await self.client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=formatted_messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )

            # Extract response
            content = response.choices[0].message.content or ""
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = (
                response.usage.completion_tokens if response.usage else 0
            )
            total_tokens = response.usage.total_tokens if response.usage else 0

            # Calculate cost
            cost = self.estimate_cost(input_tokens, output_tokens)

            # Update stats
            self.total_tokens_used += total_tokens
            self.total_cost += cost

            logger.info(
                "openai_completion",
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
                    "finish_reason": response.choices[0].finish_reason,
                },
            )

        except RateLimitError as e:
            logger.error("openai_rate_limit", error=str(e))
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            logger.error("openai_timeout", error=str(e))
            raise LLMTimeoutError(f"Request timed out: {e}") from e
        except APIError as e:
            logger.error("openai_api_error", error=str(e))
            raise LLMAPIError(f"API error: {e}") from e
        except Exception as e:
            logger.error("openai_unexpected_error", error=str(e))
            raise LLMError(f"Unexpected error: {e}") from e

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken.

        Args:
            text: Text to count

        Returns:
            Token count
        """
        return len(self.tokenizer.encode(text))

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
