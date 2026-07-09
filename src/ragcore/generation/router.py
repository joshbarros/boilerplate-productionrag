"""Generation router — provider-routed LLM calls (D7).

Supports: OpenRouter (default, free), Anthropic, OpenAI, Ollama (fallback).
Cheap-first routing with escalation flag (Constitution V).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ragcore.config import Provider, get_settings
from ragcore.generation.prompts import build_prompt
from ragcore.obs.otel import stage_span


@dataclass
class GenerationResult:
    """Raw LLM response with cost tracking."""

    text: str
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    degraded: bool = False


@stage_span("generate")
def generate_answer(
    question: str,
    passages: list[dict],
    model_override: str | None = None,
) -> GenerationResult:
    """Generate a grounded answer using the configured provider.

    Args:
        question: User's question.
        passages: Retrieved passages with chunk_id, page, text.
        model_override: Force a specific model (optional).

    Returns:
        GenerationResult with raw LLM output and cost data.
    """
    settings = get_settings()
    messages = build_prompt(question, passages)

    start = time.perf_counter()

    if settings.default_provider == Provider.OPENROUTER:
        result = _call_openrouter(settings, messages, model_override)
    elif settings.default_provider == Provider.ANTHROPIC:
        result = _call_anthropic(settings, messages, model_override)
    elif settings.default_provider == Provider.OPENAI:
        result = _call_openai(settings, messages, model_override)
    else:
        result = _call_ollama(settings, messages, model_override)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    result.latency_ms = elapsed_ms
    return result


def _call_openrouter(
    settings, messages, model_override: str | None
) -> GenerationResult:
    """Call OpenRouter (OpenAI-compatible API, free models available)."""
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    model = model_override or settings.openrouter_default_model

    # Disable reasoning chain → fast clean JSON output (reasoning effort = none)
    # Set to "low"/"high" in config for complex tasks needing chain-of-thought
    extra: dict = {}
    if settings.openrouter_reasoning_effort != "auto":
        extra["reasoning"] = {"effort": settings.openrouter_reasoning_effort}

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=2000,
        response_format={"type": "json_object"},
        extra_body=extra if extra else None,
    )

    content = ""
    if response.choices and len(response.choices) > 0:
        content = response.choices[0].message.content or ""

    return GenerationResult(
        text=content,
        model_used=response.model or model,
        prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
        completion_tokens=response.usage.completion_tokens if response.usage else 0,
        latency_ms=0,  # set by caller
    )


def _call_anthropic(settings, messages, model_override: str | None) -> GenerationResult:
    """Call Anthropic directly."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    model = model_override or settings.anthropic_default_model

    system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=system_msg,
        messages=user_msgs,
    )

    return GenerationResult(
        text=response.content[0].text if response.content else "",
        model_used=model,
        prompt_tokens=response.usage.input_tokens,
        completion_tokens=response.usage.output_tokens,
        latency_ms=0,
    )


def _call_openai(settings, messages, model_override: str | None) -> GenerationResult:
    """Call OpenAI directly."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    model = model_override or settings.openai_default_model

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    content = ""
    if response.choices and len(response.choices) > 0:
        content = response.choices[0].message.content or ""

    return GenerationResult(
        text=content,
        model_used=response.model,
        prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
        completion_tokens=response.usage.completion_tokens if response.usage else 0,
        latency_ms=0,
    )


def _call_ollama(settings, messages, model_override: str | None) -> GenerationResult:
    """Call Ollama (local fallback, FR-013)."""
    import ollama

    model = model_override or settings.ollama_model
    response = ollama.chat(model=model, messages=messages)

    return GenerationResult(
        text=response["message"]["content"],
        model_used=model,
        prompt_tokens=response.get("prompt_eval_count", 0),
        completion_tokens=response.get("eval_count", 0),
        latency_ms=0,
        degraded=True,
    )
