"""Anthropic provider configuration for Stille Post."""

from gcp_secrets import SecretsContainer
from provider import create_provider
from models import PROVIDER_MODELS

secret = SecretsContainer()

provider = create_provider(
    name="anthropic",
    api_key=secret.ANTHROPIC_API_KEY,
    models=PROVIDER_MODELS["anthropic"],
)

if __name__ == "__main__":
    # Quick test: ask each model who it is
    messages = [{"role": "user", "content": "Who are you? Answer in one sentence."}]
    for model in provider.config.models:
        try:
            result = provider.generate(messages=messages, model=model)
            print(f"[{model}]: {result['content'][:120]}")
        except Exception as e:
            print(f"[{model}]: ERROR - {e}")
