from __future__ import annotations

import os
import sys
from pathlib import Path

DATA_DIR_ENV_VAR = "MATH_TRAINER_DATA_DIR"
APP_DATA_DIR_NAME = "mental-math-trainer"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resolve_static_dir() -> Path:
    if is_frozen():
        bundle_dir = Path(getattr(sys, "_MEIPASS"))  # type: ignore[attr-defined]
        return bundle_dir / "app" / "static"
    return Path(__file__).resolve().parent / "static"


def resolve_data_dir() -> Path:
    configured_path = os.environ.get(DATA_DIR_ENV_VAR)
    if configured_path:
        return Path(configured_path).expanduser()

    repo_root = _resolve_repo_root()
    if repo_root is not None:
        return repo_root / "data"

    return _resolve_user_data_dir()


def _resolve_repo_root() -> Path | None:
    root = Path(__file__).resolve().parents[1]
    if (root / "app").is_dir() and (root / "requirements.txt").exists():
        return root
    return None


def _resolve_user_data_dir() -> Path:
    if sys.platform == "win32":
        base_dir = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base_dir:
            return Path(base_dir) / APP_DATA_DIR_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DATA_DIR_NAME

    base_dir = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base_dir / APP_DATA_DIR_NAME
