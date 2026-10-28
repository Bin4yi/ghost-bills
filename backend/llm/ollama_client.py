"""Tiny client for a local Ollama server. Nothing here talks to the internet."""

from __future__ import annotations

import json
from typing import Any

import httpx

from backend import settings


class OllamaError(RuntimeError):
    pass


def _fix_hint() -> str:
    return f"Start Ollama, then run: ollama pull {settings.OLLAMA_MODEL}"


def ping() -> dict[str, Any]:
    """Check that Ollama runs and the model is pulled. Raises OllamaError with a fix."""
    try:
        r = httpx.get(f"{settings.OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
    except httpx.HTTPError as err:
        raise OllamaError(f"Ollama is not running ({err}). {_fix_hint()}") from err
    names = {m.get("name") for m in r.json().get("models", [])}
    model = settings.OLLAMA_MODEL
    if model not in names and f"{model}:latest" not in names:
        raise OllamaError(f"Model {model} is missing. Run: ollama pull {model}")
    return {"ok": True, "model": model}


def chat_json(system: str, user: str, schema: dict[str, Any],
              timeout: float = 60.0) -> dict[str, Any]:
    """Ask the model for JSON that follows `schema` (Ollama structured output)."""
    body = {
        "model": settings.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "format": schema,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        r = httpx.post(f"{settings.OLLAMA_URL}/api/chat", json=body, timeout=timeout)
        r.raise_for_status()
    except httpx.HTTPError as err:
        raise OllamaError(f"Ollama call failed ({err}). {_fix_hint()}") from err
    content = r.json().get("message", {}).get("content", "")
    try:
        return json.loads(content)
    except json.JSONDecodeError as err:
        raise OllamaError(f"Model did not return JSON: {content[:200]}") from err
