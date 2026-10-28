"""App settings read from the environment."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "120"))
DB_PATH = Path(os.environ.get("GHOST_DB", str(ROOT / "ghost_bills.db")))


def today() -> date:
    """The fixed 'today' used by detection. Never date.today() in detect/."""
    return date.fromisoformat(os.environ.get("DEMO_TODAY", "2026-10-27"))
