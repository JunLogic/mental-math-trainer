from __future__ import annotations

import secrets
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
from math import ceil
from threading import Lock
from typing import Optional

from app.models.game import GameSession
from app.services.config import GenerationSettings
from app.services.generator import QuestionGenerator
from app.services.storage import SQLiteStorage


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionManager:
    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage
        self.sessions: dict[str, GameSession] = {}
        self.lock = Lock()

    def start_session(self, settings: GenerationSettings) -> GameSession:
        now = utc_now()
        seed = secrets.randbelow(1_000_000_000)
        session_id = secrets.token_urlsafe(12)
        generator = QuestionGenerator(settings=settings, seed=seed)
        questions = generator.generate_run()
        questions[0].presented_at = now

        session = GameSession(
            session_id=session_id,
            seed=seed,
            mode=settings.mode,
            created_at=now,
            started_at=now,
            expires_at=now + timedelta(seconds=settings.duration_seconds),
            current_index=0,
            score=0,
            raw_score=0,
            correct=0,
            incorrect=0,
            unanswered=0,
            attempted=0,
            questions=questions,
            generation_settings=settings.to_dict(),
        )

        with self.lock:
            self._cleanup_stale_sessions(now)
            self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> GameSession:
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise KeyError("Session not found.")
            self._finalize_if_expired(session)
            return session

    def answer_question(
        self,
        session_id: str,
        selected_option_index: Optional[int] = None,
        submitted_answer: Optional[str] = None,
    ) -> GameSession:
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise KeyError("Session not found.")

            if session.finished:
                return session

            now = utc_now()
            if now >= session.expires_at:
                self._finalize_session(session=session, now=now, reason="time_expired")
                return session

            if session.current_index >= session.total_questions:
                self._finalize_session(session=session, now=now, reason="question_limit")
                return session

            current_question = session.questions[session.current_index]
            if current_question.presented_at is None:
                current_question.presented_at = now

            is_correct = self._evaluate_answer(
                session=session,
                submitted_answer=submitted_answer,
                selected_option_index=selected_option_index,
            )
            current_question.answered_at = now
            current_question.response_time_ms = max(
                0,
                int((now - current_question.presented_at).total_seconds() * 1000),
            )
            session.attempted += 1

            if is_correct:
                current_question.result = "correct"
                session.correct += 1
                session.score += 1
                session.raw_score += 1
            else:
                current_question.result = "incorrect"
                session.incorrect += 1
                if session.mode != "zetamac":
                    session.score -= 1

            session.current_index += 1

            if session.current_index >= session.total_questions:
                self._finalize_session(session=session, now=now, reason="question_limit")
                return session

            next_question = session.questions[session.current_index]
            next_question.presented_at = now
            return session

    def _evaluate_answer(
        self,
        session: GameSession,
        submitted_answer: Optional[str],
        selected_option_index: Optional[int],
    ) -> bool:
        current_question = session.questions[session.current_index]

        if session.mode == "training":
            if selected_option_index not in {0, 1, 2, 3}:
                raise ValueError("selected_option_index must be between 0 and 3 for training mode.")
            current_question.selected_option = selected_option_index
            current_question.submitted_answer = current_question.options[selected_option_index]
            return selected_option_index == current_question.correct_option_index

        if session.mode == "zetamac":
            parsed_answer = parse_integer_answer(submitted_answer)
            current_question.submitted_answer = submitted_answer.strip() if submitted_answer is not None else None
            return parsed_answer == parse_integer_answer(current_question.correct_answer)

        parsed_answer = parse_numeric_answer(submitted_answer)
        current_question.submitted_answer = submitted_answer.strip() if submitted_answer is not None else None
        return parsed_answer == parse_numeric_answer(current_question.correct_answer)

    def finish_session(self, session_id: str, reason: str = "manual_finish") -> GameSession:
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise KeyError("Session not found.")
            self._finalize_session(session=session, now=utc_now(), reason=reason)
            return session

    def abort_session(self, session_id: str) -> None:
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if session is None:
                raise KeyError("Session not found.")

    def _finalize_if_expired(self, session: GameSession) -> None:
        if session.finished:
            return
        now = utc_now()
        if now >= session.expires_at:
            self._finalize_session(session=session, now=now, reason="time_expired")

    def _finalize_session(self, session: GameSession, now: datetime, reason: str) -> None:
        if session.finished:
            return

        self._mark_current_question_unanswered(session=session, now=now)
        session.finished = True
        session.finalized_at = now
        session.finish_reason = reason

        if not session.leaderboard_saved:
            self.storage.save_run(session)
            session.leaderboard_saved = True

    def _mark_current_question_unanswered(self, session: GameSession, now: datetime) -> None:
        if session.current_index >= session.total_questions:
            return

        current_question = session.questions[session.current_index]
        if current_question.presented_at is None or current_question.result is not None:
            return

        current_question.result = "unanswered"
        current_question.answered_at = now
        session.unanswered += 1

    def _cleanup_stale_sessions(self, now: datetime) -> None:
        stale_ids = [
            session_id
            for session_id, session in self.sessions.items()
            if (session.finished and session.finalized_at and now - session.finalized_at > timedelta(hours=1))
            or (not session.finished and now - session.created_at > timedelta(hours=4))
        ]
        for session_id in stale_ids:
            self.sessions.pop(session_id, None)

    def build_session_payload(self, session: GameSession, include_history: bool = False) -> dict[str, object]:
        now = utc_now()
        if not session.finished and now >= session.expires_at:
            with self.lock:
                self._finalize_session(session=session, now=now, reason="time_expired")

        payload = session.summary()
        payload["remaining_seconds"] = max(
            0,
            ceil((session.expires_at - now).total_seconds()),
        ) if not session.finished else 0

        current_question = session.current_question()
        payload["question"] = (
            current_question.to_public(session.current_index + 1, session.total_questions, session.mode)
            if current_question is not None
            else None
        )

        if include_history:
            payload["history"] = [
                question.to_history_row(index + 1)
                for index, question in enumerate(session.questions)
                if question.presented_at is not None
            ]
        return payload


def parse_numeric_answer(value: Optional[str]) -> Decimal:
    if value is None:
        raise ValueError("An answer is required in assessment mode.")

    cleaned = value.strip().replace(",", "").replace("−", "-")
    if not cleaned:
        raise ValueError("An answer is required in assessment mode.")

    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("Answer must be a valid integer or decimal value.") from exc


def parse_integer_answer(value: Optional[str]) -> int:
    parsed = parse_numeric_answer(value)
    if parsed != parsed.to_integral_value():
        raise ValueError("Zetamac answers must be whole numbers.")
    return int(parsed)
