"""
Unified LLM provider using OpenAI SDK for all three backends.

Since OpenAI, Anthropic, and Google all support the OpenAI chat completions
format, we use a single provider class. Only base_url and api_key differ.
"""

from openai import OpenAI
from models import ProviderConfig, GAME_TOOLS, PROVIDER_ENDPOINTS


class UnifiedLLMProvider:
    """
    Single provider that works with OpenAI, Anthropic, and Google
    via their OpenAI-compatible endpoints.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def generate(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict] | None = None,
    ) -> dict:
        """
        Generate a response using the OpenAI chat completions format.

        Args:
            messages: OpenAI-format messages [{"role": ..., "content": ...}]
            model: Model identifier (e.g. "gpt-5-nano", "gemini-3-flash-preview")
            tools: Optional tool definitions in OpenAI format.

        Returns:
            dict with 'content' (str) and optionally 'tool_calls' (list).
        """
        kwargs = {
            "model": model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        result = {
            "content": choice.message.content or "",
            "tool_calls": [],
        }

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,  # JSON string
                })

        return result


def create_provider(name: str, api_key: str, models: list[str]) -> UnifiedLLMProvider:
    """Helper to create a provider by name."""
    if name not in PROVIDER_ENDPOINTS:
        raise ValueError(f"Unknown provider: {name}. Must be one of {list(PROVIDER_ENDPOINTS.keys())}")

    config = ProviderConfig(
        name=name,
        base_url=PROVIDER_ENDPOINTS[name],
        api_key=api_key,
        models=models,
    )
    return UnifiedLLMProvider(config)
