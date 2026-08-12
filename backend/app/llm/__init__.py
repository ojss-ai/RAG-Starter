from typing import AsyncIterator, Protocol

from app.config import Settings


class LLMProvider(Protocol):
    def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]: ...


def get_llm_provider(settings: Settings) -> LLMProvider:
    from app.llm.providers import AnthropicLLMProvider, FakeLLMProvider, OpenAILLMProvider
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAILLMProvider(settings.llm_api_base, settings.llm_api_key,
                                 settings.llm_model)
    if settings.llm_provider == "anthropic":
        return AnthropicLLMProvider(settings.llm_api_key, settings.llm_model)
    if settings.llm_provider == "local":
        # Ollama / LM Studio / vLLM / llama.cpp all speak the OpenAI /chat/completions
        # shape — no API key needed, most local servers ignore the auth header.
        return OpenAILLMProvider(settings.llm_api_base, settings.llm_api_key or "local",
                                 settings.llm_model)
    raise ValueError(f"unknown llm provider: {settings.llm_provider}")
