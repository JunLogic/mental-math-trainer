from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.runtime import resolve_data_dir, resolve_static_dir
from app.services.storage import SQLiteStorage
from app.services.session_manager import SessionManager

STATIC_DIR = resolve_static_dir()
_DATA_DIR = resolve_data_dir()
DATABASE_PATH = _DATA_DIR / "leaderboard.db"


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
    debug=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
