from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.schemas import GameAbortRequest, GameAnswerRequest, GameFinishRequest, GameStartRequest
from app.services.config import GenerationSettings, deep_merge_dicts, load_default_settings
from app.services.session_manager import SessionManager

router = APIRouter(prefix="/api")


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager


def resolve_settings(payload: Optional[GameStartRequest]) -> GenerationSettings:
    if payload is not None and payload.mode == "zetamac":
        overrides: dict[str, object] = {}
        if payload.zetamac_settings is not None:
            overrides["zetamac_settings"] = payload.zetamac_settings.model_dump(exclude_none=True)
        settings = GenerationSettings.for_zetamac(overrides)
    elif payload is not None and payload.preset_name is not None:
        settings = GenerationSettings.from_preset(payload.preset_name, mode=payload.mode)
    else:
        settings = load_default_settings()
        if payload is not None and payload.mode is not None:
            settings.mode = payload.mode

    if payload is not None:
        if payload.adaptive_enabled is not None:
            settings.adaptive_enabled = payload.adaptive_enabled
        if payload.target_pace_seconds is not None:
            settings.target_pace_seconds = payload.target_pace_seconds
        if payload.initial_difficulty is not None:
            settings.initial_difficulty = payload.initial_difficulty

    if payload is None or payload.settings is None:
        settings.validate()
        return settings

    overrides = payload.settings.model_dump(exclude_none=True)
    merged = settings.to_dict()
    merged.pop("normalized", None)
    merged = deep_merge_dicts(merged, overrides)
    return GenerationSettings.from_dict(merged)


@router.post("/game/start")
def start_game(request: Request, payload: Optional[GameStartRequest] = None) -> dict[str, object]:
    try:
        settings = resolve_settings(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session = get_session_manager(request).start_session(settings)
    return get_session_manager(request).build_session_payload(session)


@router.post("/game/answer")
def answer_question(request: Request, payload: GameAnswerRequest) -> dict[str, object]:
    session_manager = get_session_manager(request)
    try:
        session = session_manager.answer_question(
            session_id=payload.session_id,
            selected_option_index=payload.selected_option_index,
            submitted_answer=payload.answer,
            question_number=payload.question_number,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return session_manager.build_session_payload(session, include_history=session.finished)


@router.get("/game/state/{session_id}")
def game_state(request: Request, session_id: str) -> dict[str, object]:
    session_manager = get_session_manager(request)
    try:
        session = session_manager.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return session_manager.build_session_payload(session, include_history=session.finished)


@router.post("/game/finish")
def finish_game(request: Request, payload: GameFinishRequest) -> dict[str, object]:
    session_manager = get_session_manager(request)
    try:
        session = session_manager.finish_session(payload.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return session_manager.build_session_payload(session, include_history=True)


@router.post("/game/abort")
def abort_game(request: Request, payload: GameAbortRequest) -> dict[str, object]:
    session_manager = get_session_manager(request)
    try:
        session_manager.abort_session(payload.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"aborted": True}


@router.get("/leaderboard")
def leaderboard(request: Request, limit: int = Query(default=10, ge=1, le=50)) -> dict[str, object]:
    storage = request.app.state.storage
    return {"items": storage.leaderboard(limit=limit)}
