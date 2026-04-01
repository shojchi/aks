"""LLM client — supports Gemini (default) and Anthropic."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class ModelConfig:
    model: str
    max_tokens: int
    temperature: float
    provider: str = "gemini"  # "gemini" | "anthropic"


# ---------------------------------------------------------------------------
# Gemini (google-genai SDK)
# ---------------------------------------------------------------------------

def _gemini_client() -> Any:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set")
    from google import genai
    return genai.Client(api_key=api_key)


def _gemini_complete(client: Any, config: ModelConfig, system: str, messages: list[dict]) -> str:
    from google.genai import types

    # Convert messages to Gemini Content format
    # Gemini uses "model" instead of "assistant"
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else msg["role"]
        contents.append(
            types.Content(role=role, parts=[types.Part(text=msg["content"])])
        )

    response = client.models.generate_content(
        model=config.model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=config.max_tokens,
            temperature=config.temperature,
        ),
    )
    return response.text


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

def _anthropic_client() -> Any:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set")
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def _anthropic_complete(client: Any, config: ModelConfig, system: str, messages: list[dict]) -> str:
    response = client.messages.create(
        model=config.model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        system=system,
        messages=messages,
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Unified interface
# ---------------------------------------------------------------------------

_clients: dict[str, Any] = {}


def get_client(provider: str = "gemini") -> Any:
    if provider not in _clients:
        if provider == "gemini":
            _clients[provider] = _gemini_client()
        elif provider == "anthropic":
            _clients[provider] = _anthropic_client()
        else:
            raise ValueError(f"Unknown provider: {provider!r}")
    return _clients[provider]


def complete(
    client: Any,
    config: ModelConfig,
    system: str,
    messages: list[dict],
) -> str:
    if config.provider == "gemini":
        return _gemini_complete(client, config, system, messages)
    return _anthropic_complete(client, config, system, messages)
