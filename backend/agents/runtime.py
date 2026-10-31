"""Everything the agents need, built once per app."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from backend.agents.gateway import Auth0Gateway, Gateway
from backend.agents.vault import AgentTokens
from backend.auth.config import AuthSettings
from backend.auth.tokens import Verifier


@dataclass
class AgentRuntime:
    settings: AuthSettings
    verifier: Verifier
    gateway: Gateway
    tokens: AgentTokens = field(default_factory=AgentTokens)
    gmail: Any = None  # set in courier (Phase 4); tests swap in a fake


def build(settings: AuthSettings) -> AgentRuntime:
    from backend.agents.gmail import GmailSender
    return AgentRuntime(settings=settings, verifier=Verifier(settings),
                        gateway=Auth0Gateway(settings), gmail=GmailSender())


def runtime(request: Request) -> AgentRuntime:
    return request.app.state.agents
