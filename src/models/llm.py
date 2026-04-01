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
# Gemini
# ---------------------------------------------------------------------------

def _gemini_client() -> Any:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set")
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    return genai


def _gemini_complete(genai: Any, config: ModelConfig, system: str, messages: list[dict]) -> str:
    import google.generativeai as genai_module

    model = genai_module.GenerativeModel(
        model_name=config.model,
        system_instruction=system,
        generation_config=genai_module.GenerationConfig(
            max_output_tokens=config.max_tokens,
            temperature=config.temperature,
        ),
    )

    # Convert Anthropic-style messages to Gemini history format
    # Gemini uses "model" instead of "assistant"
    history = []
    for msg in messages[:-1]:
        role = "model" if msg["role"] == "assistant" else msg["role"]
        history.append({"role": role, "parts": [msg["content"]]})

    last_message = messages[-1]["content"] if messages else ""

    if history:
        chat = model.start_chat(history=history)
        response = chat.send_message(last_message)
    else:
        response = model.generate_content(last_message)

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
