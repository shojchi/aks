"""Thin wrapper around the Anthropic SDK."""
from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic


@dataclass
class ModelConfig:
    model: str
    max_tokens: int
    temperature: float


def get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


def complete(
    client: anthropic.Anthropic,
    config: ModelConfig,
    system: str,
    messages: list[dict],
) -> str:
    response = client.messages.create(
        model=config.model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        system=system,
        messages=messages,
    )
    return response.content[0].text
