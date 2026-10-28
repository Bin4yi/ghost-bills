"""FastAPI routes for Ghost Bills."""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import settings
from backend.importer import csv_import, service
from backend.models import ColumnMapping, ImportPreview

app = FastAPI(title="Ghost Bills")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "model": settings.OLLAMA_MODEL}


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
