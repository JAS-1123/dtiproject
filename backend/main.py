from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.aiml import answer_question, make_recap

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(__file__).resolve().parent / "data"
FRONTEND_DIST = ROOT / "frontend" / "dist"
AUDIO_DIR = (FRONTEND_DIST / "audio") if (FRONTEND_DIST / "audio").exists() else (ROOT / "frontend" / "public" / "audio")
DEFAULT_BOOK_ID = os.getenv("DEFAULT_BOOK_ID", "pride-and-prejudice")


def load_books() -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            item = json.load(file)
        book_id = str(item.get("id", "")).strip()
        if book_id:
            loaded[book_id] = item
    if not loaded:
        raise RuntimeError(f"No book JSON files found in {DATA_DIR}")
    if DEFAULT_BOOK_ID not in loaded:
        # Fall back to the first available book rather than failing deployment.
        print(f"WARNING: DEFAULT_BOOK_ID={DEFAULT_BOOK_ID!r} not found; using {next(iter(loaded))!r}")
    return loaded


BOOKS = load_books()
if DEFAULT_BOOK_ID not in BOOKS:
    DEFAULT_BOOK_ID = next(iter(BOOKS))

app = FastAPI(
    title="LoreFlow API",
    description="Position-aware, spoiler-safe audiobook companion with a selectable demo library.",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    position_sec: float = Field(ge=0)
    book_id: str = Field(default=DEFAULT_BOOK_ID, min_length=1, max_length=100)
    context_questions: list[str] = Field(default_factory=list, max_length=4)


class PositionRequest(BaseModel):
    position_sec: float = Field(ge=0)
    book_id: str = Field(default=DEFAULT_BOOK_ID, min_length=1, max_length=100)


def get_book_or_404(book_id: str | None) -> dict[str, Any]:
    key = book_id or DEFAULT_BOOK_ID
    book = BOOKS.get(key)
    if book is None:
        raise HTTPException(status_code=404, detail=f"Unknown book: {key}")
    return book


def clamp_position(position_sec: float, book: dict[str, Any]) -> float:
    return max(0.0, min(float(position_sec), float(book["duration_sec"])))


def public_book(book: dict[str, Any]) -> dict[str, Any]:
    """Return UI metadata and timing labels, never transcript passage text."""
    public = {
        key: value
        for key, value in book.items()
        if key not in {"facts", "chunks", "source_credit", "license_note"}
    }
    public["chunks"] = [
        {key: value for key, value in chunk.items() if key != "text"}
        for chunk in book.get("chunks", [])
    ]
    return public


@app.get("/api/health")
def health() -> dict[str, str]:
    has_grok = bool(os.getenv("XAI_API_KEY", "").strip())
    return {
        "status": "ok",
        "service": "LoreFlow",
        "version": "1.2.0",
        "answer_engine": "xAI Grok" if has_grok else "Local retrieval",
        "default_book_id": DEFAULT_BOOK_ID,
    }


@app.get("/api/books")
def get_books() -> dict[str, Any]:
    summaries = []
    for book in BOOKS.values():
        summaries.append({
            "id": book["id"],
            "title": book["title"],
            "author": book["author"],
            "genre": book.get("genre", ""),
            "description": book.get("description", ""),
            "duration_sec": book["duration_sec"],
            "cover_style": book.get("cover_style", "fantasy"),
        })
    return {"default_book_id": DEFAULT_BOOK_ID, "books": summaries}


@app.get("/api/book")
def get_book(book_id: str | None = Query(default=None)) -> dict[str, Any]:
    return public_book(get_book_or_404(book_id))


@app.post("/api/ask")
def ask(request: AskRequest) -> dict[str, Any]:
    book = get_book_or_404(request.book_id)
    position = clamp_position(request.position_sec, book)
    try:
        result = answer_question(
            request.question,
            position,
            book,
            context_questions=request.context_questions,
        )
        result["book_id"] = book["id"]
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to answer right now. Please try again.") from exc


@app.post("/api/recap")
def recap(request: PositionRequest) -> dict[str, Any]:
    book = get_book_or_404(request.book_id)
    return make_recap(clamp_position(request.position_sec, book), book)


if AUDIO_DIR.exists():
    app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}")
    def frontend(full_path: str):
        requested = FRONTEND_DIST / full_path
        if full_path and requested.is_file() and FRONTEND_DIST in requested.parents:
            return FileResponse(requested)
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build in frontend/.")
else:
    @app.get("/")
    def root():
        return {
            "service": "LoreFlow API",
            "message": "Run the React dev server with: cd frontend && npm install && npm run dev",
            "api_docs": "/docs",
        }
