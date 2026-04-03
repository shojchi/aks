"""LLM client — supports Cerebras (default) and Gemini with automatic fallback."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Iterator


@dataclass
class ModelConfig:
    model: str
    max_tokens: int
    temperature: float
    provider: str = "cerebras"  # "cerebras" | "gemini"


# ---------------------------------------------------------------------------
# Cerebras (OpenAI-compatible)
# ---------------------------------------------------------------------------

def _cerebras_client() -> Any:
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise EnvironmentError("CEREBRAS_API_KEY is not set")
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url="https://api.cerebras.ai/v1")


def _cerebras_complete(
    client: Any, config: ModelConfig, system: str, messages: list[dict]
) -> tuple[str, int, int]:
    response = client.chat.completions.create(
        model=config.model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        messages=[{"role": "system", "content": system}] + messages,
    )
    in_tok = response.usage.prompt_tokens if response.usage else 0
    out_tok = response.usage.completion_tokens if response.usage else 0
    return response.choices[0].message.content, in_tok, out_tok


def _cerebras_stream(
    client: Any, config: ModelConfig, system: str, messages: list[dict]
) -> Iterator[tuple[str, int, int]]:
    """Yield (chunk, 0, 0) per chunk; final item is ("", in_tok, out_tok)."""
    in_tok = out_tok = 0
    with client.chat.completions.create(
        model=config.model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        messages=[{"role": "system", "content": system}] + messages,
        stream=True,
        stream_options={"include_usage": True},
    ) as s:
        for chunk in s:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content, 0, 0
            if getattr(chunk, "usage", None):
                in_tok = chunk.usage.prompt_tokens or 0
                out_tok = chunk.usage.completion_tokens or 0
    yield "", in_tok, out_tok


# ---------------------------------------------------------------------------
# Gemini (google-genai SDK)
# ---------------------------------------------------------------------------

def _gemini_client() -> Any:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set")
    from google import genai
    return genai.Client(api_key=api_key)


def _gemini_contents(messages: list[dict]) -> list:
    from google.genai import types
    return [
        types.Content(
            role="model" if m["role"] == "assistant" else m["role"],
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]


def _gemini_complete(
    client: Any, config: ModelConfig, system: str, messages: list[dict]
) -> tuple[str, int, int]:
    from google.genai import types

    response = client.models.generate_content(
        model=config.model,
        contents=_gemini_contents(messages),
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=config.max_tokens,
            temperature=config.temperature,
        ),
    )
    usage = response.usage_metadata
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    return response.text, in_tok, out_tok


def _gemini_stream(
    client: Any, config: ModelConfig, system: str, messages: list[dict]
) -> Iterator[tuple[str, int, int]]:
    """Yield (chunk, 0, 0) per chunk; final item is ("", in_tok, out_tok)."""
    from google.genai import types

    in_tok = out_tok = 0
    for chunk in client.models.generate_content_stream(
        model=config.model,
        contents=_gemini_contents(messages),
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=config.max_tokens,
            temperature=config.temperature,
        ),
    ):
        if chunk.text:
            yield chunk.text, 0, 0
        usage = getattr(chunk, "usage_metadata", None)
        if usage:
            in_tok = getattr(usage, "prompt_token_count", 0) or 0
            out_tok = getattr(usage, "candidates_token_count", 0) or 0
    yield "", in_tok, out_tok


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def get_embedding(text: str, provider: str = "gemini") -> list[float]:
    """Return a dense embedding vector for the given text."""
    if provider == "gemini":
        from google import genai
        from aks.utils.config import models_config
        from aks.utils.cost import CostLedger

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY is not set")
        client = genai.Client(api_key=api_key)
        model = models_config()["embeddings"]["model"]
        result = client.models.embed_content(model=model, contents=text)

        usage = getattr(result, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) or 0 if usage else 0
        if in_tok:
            CostLedger().record("gemini", model, in_tok, 0)

        return list(result.embeddings[0].values)
    raise ValueError(f"Embeddings not supported for provider: {provider!r}")


# ---------------------------------------------------------------------------
# Unified interface
# ---------------------------------------------------------------------------

_clients: dict[str, Any] = {}


def get_client(provider: str = "cerebras") -> Any:
    if provider not in _clients:
        if provider == "cerebras":
            _clients[provider] = _cerebras_client()
        elif provider == "gemini":
            _clients[provider] = _gemini_client()
        else:
            raise ValueError(f"Unknown provider: {provider!r}")
    return _clients[provider]


def _is_rate_limited(exc: Exception) -> bool:
    """Detect quota / rate-limit errors across all providers."""
    cls_name = type(exc).__name__
    msg = str(exc)
    # OpenAI SDK (Cerebras uses this)
    if cls_name == "RateLimitError":
        return True
    # Gemini google-genai SDK
    if cls_name == "ClientError" and ("429" in msg or "RESOURCE_EXHAUSTED" in msg):
        return True
    return False


def _build_fallbacks(primary_provider: str, primary_config: ModelConfig) -> list[tuple[Any, ModelConfig]]:
    """Build (client, config) pairs for each fallback provider, skipping the primary."""
    from aks.utils.config import get_fallback_chain
    result = []
    for fb in get_fallback_chain():
        provider = fb["provider"]
        if provider == primary_provider:
            continue
        fb_config = ModelConfig(
            model=fb["model"],
            max_tokens=primary_config.max_tokens,
            temperature=primary_config.temperature,
            provider=provider,
        )
        result.append((get_client(provider), fb_config))
    return result


def _call_complete(
    client: Any, config: ModelConfig, system: str, messages: list[dict]
) -> tuple[str, int, int]:
    if config.provider == "cerebras":
        return _cerebras_complete(client, config, system, messages)
    if config.provider == "gemini":
        return _gemini_complete(client, config, system, messages)
    raise ValueError(f"Unknown provider: {config.provider!r}")


def _call_stream(
    client: Any, config: ModelConfig, system: str, messages: list[dict]
) -> Iterator[tuple[str, int, int]]:
    if config.provider == "cerebras":
        return _cerebras_stream(client, config, system, messages)
    if config.provider == "gemini":
        return _gemini_stream(client, config, system, messages)
    raise ValueError(f"Unknown provider: {config.provider!r}")


def complete(
    client: Any,
    config: ModelConfig,
    system: str,
    messages: list[dict],
) -> str:
    from aks.utils.cost import CostLedger

    attempts = [(client, config)] + _build_fallbacks(config.provider, config)

    for i, (c, cfg) in enumerate(attempts):
        is_last = i == len(attempts) - 1
        try:
            text, in_tok, out_tok = _call_complete(c, cfg, system, messages)
            if in_tok or out_tok:
                CostLedger().record(cfg.provider, cfg.model, in_tok, out_tok)
            if i > 0:
                print(f"[using {cfg.provider}/{cfg.model}]", file=sys.stderr)
            return text
        except Exception as exc:
            if _is_rate_limited(exc) and not is_last:
                next_provider = attempts[i + 1][1].provider
                print(
                    f"\n[{cfg.provider} quota exhausted → falling back to {next_provider}…]",
                    file=sys.stderr,
                )
                continue
            raise

    raise RuntimeError("All providers exhausted")  # never reached


def stream(
    client: Any,
    config: ModelConfig,
    system: str,
    messages: list[dict],
) -> Iterator[str]:
    """Yield text chunks as they arrive; falls back on quota errors."""
    from aks.utils.cost import CostLedger

    attempts = [(client, config)] + _build_fallbacks(config.provider, config)

    for i, (c, cfg) in enumerate(attempts):
        is_last = i == len(attempts) - 1
        in_tok = out_tok = 0
        try:
            for chunk, it, ot in _call_stream(c, cfg, system, messages):
                if chunk:
                    yield chunk
                if it:
                    in_tok = it
                if ot:
                    out_tok = ot
            if in_tok or out_tok:
                CostLedger().record(cfg.provider, cfg.model, in_tok, out_tok)
            return
        except Exception as exc:
            if _is_rate_limited(exc) and not is_last:
                next_provider = attempts[i + 1][1].provider
                print(
                    f"\n[{cfg.provider} quota exhausted → falling back to {next_provider}…]",
                    file=sys.stderr,
                )
                continue
            raise

    raise RuntimeError("All providers exhausted")  # never reached
