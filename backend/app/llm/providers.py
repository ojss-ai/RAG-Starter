import json
from typing import AsyncIterator

import httpx


class LLMError(Exception):
    pass


class FakeLLMProvider:
    """Deterministic offline provider: answers reference source [1] when sources exist
    (the system prompt contains a numbered '[1] (' entry), matching how tests assert
    citations. Checking the bare 'Sources:' header is wrong — it is present even when
    the block is '(none)'."""

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        has_sources = any("[1] (" in m.get("content", "") for m in messages)
        if has_sources:
            reply = "Based on the provided sources, the answer is grounded in [1]."
        else:
            reply = "I could not find relevant sources for this question."
        for word in reply.split(" "):
            yield word + " "


class AnthropicLLMProvider:
    """Anthropic /v1/messages with stream=true. System-role messages are pulled out
    into the top-level `system` param; Anthropic only accepts user/assistant roles
    in `messages`."""

    def __init__(self, api_key: str, model: str, api_base: str = "https://api.anthropic.com/v1",
                 client: httpx.AsyncClient | None = None):
        self._model = model
        self._client = client or httpx.AsyncClient(
            base_url=api_base,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=120)

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        system = "\n".join(m["content"] for m in messages if m.get("role") == "system")
        chat_messages = [m for m in messages if m.get("role") != "system"]
        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": chat_messages,
            "stream": True,
        }
        if system:
            payload["system"] = system
        try:
            async with self._client.stream("POST", "/messages", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    if event.get("type") != "content_block_delta":
                        continue
                    delta = event.get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]
        except httpx.HTTPError as exc:
            raise LLMError(str(exc)) from exc


class OpenAILLMProvider:
    """OpenAI-compatible /chat/completions with stream=true."""

    def __init__(self, api_base: str, api_key: str, model: str,
                 client: httpx.AsyncClient | None = None):
        self._model = model
        self._client = client or httpx.AsyncClient(
            base_url=api_base, headers={"Authorization": f"Bearer {api_key}"}, timeout=120)

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {"model": self._model, "messages": messages, "stream": True}
        try:
            async with self._client.stream("POST", "/chat/completions",
                                           json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    delta = (json.loads(data)["choices"][0].get("delta") or {})
                    content = delta.get("content")
                    if content:
                        yield content
        except httpx.HTTPError as exc:
            raise LLMError(str(exc)) from exc
