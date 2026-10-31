"""FastAPI routes for Ghost Bills."""

from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import db, settings
from backend.agent import graph
from backend.agents import penny
from backend.agents.ledger import snapshot
from backend.agents.runtime import build as build_agents
from backend.agents.runtime import runtime
from backend.agents.vault import AgentsStopped
from backend.auth import web
from backend.auth.config import load_settings
from backend.auth.guards import Caller, agent_or_local, local_ui_only
from backend.auth.tokens import TokenError, install_log_redaction
from backend.detect import config
from backend.detect.scan import run_scan
from backend.importer import csv_import, service
from backend.llm import enrich, ollama_client
from backend.models import ColumnMapping, ImportPreview

app = FastAPI(title="Ghost Bills")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Optional Auth0 login. Without settings nothing is mounted and the app stays local-only.
AUTH = load_settings()
web.install(app, AUTH)
app.state.agents = build_agents(AUTH)
install_log_redaction()


@app.middleware("http")
async def agent_session_hooks(request: Request, call_next):
    """A fresh login wakes stopped agents. Logging out drops every agent token."""
    response = await call_next(request)
    path = request.url.path
    if path == "/auth/callback" and response.status_code < 400:
        runtime(request).tokens.resume()
    elif path == "/auth/logout":
        runtime(request).tokens.penny.clear()
        runtime(request).tokens.courier.clear()
    return response


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "model": settings.OLLAMA_MODEL}


@app.get("/api/me")
async def me(request: Request, response: Response) -> dict:
    """Who is logged in. Never returns tokens."""
    auth = request.app.state.auth_settings
    if not auth.enabled:
        return {"auth_enabled": False, "logged_in": False}
    user = await web.current_user(request, response)
    if not user:
        return {"auth_enabled": True, "logged_in": False}
    return {"auth_enabled": True, "logged_in": True,
            "name": user.get("name") or user.get("nickname") or user.get("email") or "you",
            "agents_ready": auth.agents_ready}


# --- import ----------------------------------------------------------------

@app.post("/api/import/preview")
async def import_preview(file: UploadFile = File(...)) -> ImportPreview:
    data = await file.read()
    try:
        return service.preview(data)
    except csv_import.ImportError_ as err:
        raise HTTPException(400, str(err)) from err


class CommitBody(BaseModel):
    upload_id: str
    mapping: ColumnMapping


@app.post("/api/import/commit")
def import_commit(body: CommitBody) -> dict:
    try:
        return service.commit(body.upload_id, body.mapping)
    except (csv_import.ImportError_, ValueError) as err:
        raise HTTPException(400, str(err)) from err


# --- scan, questions, statuses ------------------------------------------------

def _dump(items: list) -> list[dict]:
    return [i.model_dump(mode="json") for i in items]


@app.get("/api/scan")
def scan_route() -> dict:
    r = run_scan()
    return {
        "today": r.today.isoformat(),
        "currency": r.currency,
        "ghosts": _dump(r.ghosts),
        **r.totals(),
        "upcoming": [u | {"date": u["date"].isoformat()} for u in r.upcoming],
        "open_questions": sum(1 for q in r.questions if q.answer is None),
        "pending_enrich": r.pending_enrich,
    }


# --- Gemma ------------------------------------------------------------------

@app.get("/api/llm/status")
def llm_status() -> dict:
    try:
        return ollama_client.ping()
    except ollama_client.OllamaError as err:
        return {"ok": False, "model": settings.OLLAMA_MODEL, "error": str(err),
                "fix": f"ollama pull {settings.OLLAMA_MODEL}"}


@app.post("/api/enrich")
def enrich_route(force: bool = False) -> dict:
    r = run_scan()
    result = enrich.enrich_all(r.ghosts, r.series, force=force)
    result["categories_suggested"] = enrich.suggest_categories(r.series)
    return result


@app.get("/api/enrich/stats")
def enrich_stats() -> dict:
    return enrich.stats()


class AskBody(BaseModel):
    question: str


@app.post("/api/ask")
async def ask_route(body: AskBody, request: Request, response: Response,
                    caller: Caller = Depends(agent_or_local("read:ghosts"))) -> dict:
    """Ask Penny. Logged out: she reads the local ledger directly (offline mode).
    Logged in with agents set up: she gets her own read-only token (Lock 1) and
    reads the ledger through the API with it."""
    question = body.question[:500]
    rt = runtime(request)
    user = await web.current_user(request, response) if caller.kind == "local" else None
    if user and rt.settings.agents_ready:
        try:
            held = await penny.penny_token(rt, user["sub"], await web.user_access_token(request, response))
            ctx = await penny.ledger_context(request.app, held.token)
        except AgentsStopped:
            return {"text": "Penny is stopped. Log in again to wake her up.", "tools_used": []}
        except TokenError as err:
            raise HTTPException(err.status, err.message) from err
        return await run_in_threadpool(graph.ask, question, ctx=ctx)
    return await run_in_threadpool(graph.ask, question)


@app.get("/api/agent/ledger")
def agent_ledger(caller: Caller = Depends(agent_or_local("read:ghosts"))) -> dict:
    """Ledger's read-only view, for Penny's tools (needs read:ghosts)."""
    return snapshot()


@app.get("/api/ghosts")
def ghosts_route(caller: Caller = Depends(agent_or_local("read:ghosts"))) -> list[dict]:
    return _dump(run_scan().ghosts)


@app.post("/api/agents/stop")
def stop_agents(request: Request, caller: Caller = Depends(local_ui_only)) -> dict:
    """Clear every agent token and block new exchanges until the next login."""
    runtime(request).tokens.stop()
    return {"stopped": True}


@app.get("/api/agents/tokens")
async def agent_tokens(request: Request, response: Response,
                       caller: Caller = Depends(local_ui_only)) -> dict:
    """'Who can do what right now': decoded claims only, never a token."""
    user = await web.current_user(request, response)
    return runtime(request).tokens.inspector(user.get("sub") if user else None)


class CategoryBody(BaseModel):
    category: str


@app.post("/api/series/{key:path}/category")
def category_route(key: str, body: CategoryBody) -> dict:
    """The user confirms (or changes) a category. Twin rules use it at once."""
    db.put("categories", "merchant_key", key, category=body.category.strip().lower(),
           source="user")
    return {"ok": True}


@app.get("/api/series")
def series_route() -> list[dict]:
    return [s.model_dump(mode="json") | {"yearly_cents": s.yearly_cents}
            for s in run_scan().series]


@app.get("/api/config")
def config_route() -> dict:
    return config.as_dict()


@app.get("/api/questions")
def questions_route() -> list[dict]:
    return _dump(run_scan().questions)


class AnswerBody(BaseModel):
    choice: Literal["a", "b"] | None


@app.post("/api/questions/{qid:path}/answer")
def answer_route(qid: str, body: AnswerBody) -> dict:
    if body.choice is None:
        db.delete("answers", "question_id", qid)
    else:
        db.put("answers", "question_id", qid, answer=body.choice)
    if qid.startswith("date_order:"):
        service.reimport_with_order({"a": "dmy", "b": "mdy", None: "dmy"}[body.choice])
    return {"ok": True}


class StatusBody(BaseModel):
    status: Literal["active", "kept", "cancelled"]


@app.post("/api/ghosts/{gid:path}/status")
def status_route(gid: str, body: StatusBody, caller: Caller = Depends(local_ui_only)) -> dict:
    if body.status == "active":
        db.delete("ghost_status", "ghost_id", gid)
    else:
        when = settings.today().isoformat() if body.status == "cancelled" else None
        db.put("ghost_status", "ghost_id", gid, status=body.status, cancelled_at=when)
    return {"ok": True}


class EssentialBody(BaseModel):
    essential: bool


@app.post("/api/series/{key:path}/essential")
def essential_route(key: str, body: EssentialBody) -> dict:
    db.put("essentials", "merchant_key", key, essential=int(body.essential))
    return {"ok": True}
