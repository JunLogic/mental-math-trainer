from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.services.storage import SQLiteStorage
from app.services.session_manager import SessionManager

ROOT_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT_DIR / "app" / "static"
DATABASE_PATH = ROOT_DIR / "data" / "leaderboard.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = SQLiteStorage(DATABASE_PATH)
    storage.initialize()
    app.state.storage = storage
    app.state.session_manager = SessionManager(storage)
    yield


app = FastAPI(
    title="Mental Arithmetic Speed Trainer",
    description="Local arithmetic speed trainer with interview-style, practice, and Zetamac-inspired modes.",
    lifespan=lifespan,
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
