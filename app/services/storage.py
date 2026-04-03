from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.models.game import GameSession, normalize_mode_name
from app.services.feature_extraction import (
    extract_core_saved_question_feature_rows,
    extract_saved_question_feature_rows,
)


class SQLiteStorage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    raw_score INTEGER NOT NULL,
                    correct INTEGER NOT NULL,
                    incorrect INTEGER NOT NULL,
                    unanswered INTEGER NOT NULL,
                    attempted INTEGER NOT NULL,
                    accuracy REAL NOT NULL,
                    average_response_time REAL NOT NULL,
                    settings_json TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'assessment',
                    duration_seconds INTEGER NOT NULL DEFAULT 480
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    question_index INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    submitted_answer TEXT,
                    correct_flag INTEGER NOT NULL,
                    result_label TEXT,
                    response_time_ms INTEGER,
                    base_operation TEXT,
                    used_decimal INTEGER NOT NULL DEFAULT 0,
                    used_missing_variable INTEGER NOT NULL DEFAULT 0,
                    left_value TEXT,
                    right_value TEXT,
                    result_value TEXT,
                    answer_role TEXT,
                    family_label TEXT,
                    difficulty_tag TEXT,
                    difficulty_at_question REAL,
                    selected_option_index INTEGER,
                    correct_option_index INTEGER,
                    operation_type TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                )
                """
            )
            self._ensure_column(connection, "runs", "mode", "TEXT NOT NULL DEFAULT 'assessment'")
            self._ensure_column(connection, "runs", "duration_seconds", "INTEGER NOT NULL DEFAULT 480")
            self._ensure_column(connection, "run_questions", "result_label", "TEXT")
            self._ensure_column(connection, "run_questions", "base_operation", "TEXT")
            self._ensure_column(connection, "run_questions", "used_decimal", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "run_questions", "used_missing_variable", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "run_questions", "left_value", "TEXT")
            self._ensure_column(connection, "run_questions", "right_value", "TEXT")
            self._ensure_column(connection, "run_questions", "result_value", "TEXT")
            self._ensure_column(connection, "run_questions", "answer_role", "TEXT")
            self._ensure_column(connection, "run_questions", "family_label", "TEXT")
            self._ensure_column(connection, "run_questions", "difficulty_tag", "TEXT")
            self._ensure_column(connection, "run_questions", "difficulty_at_question", "REAL")
            self._ensure_column(connection, "run_questions", "selected_option_index", "INTEGER")
            self._ensure_column(connection, "run_questions", "correct_option_index", "INTEGER")
            self._backfill_base_operation(connection)
            self._normalize_mode_values(connection)
            connection.commit()

    def save_run(self, session: GameSession) -> None:
        summary = session.summary()
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO runs (
                    created_at,
                    score,
                    raw_score,
                    correct,
                    incorrect,
                    unanswered,
                    attempted,
                    accuracy,
                    average_response_time,
                    settings_json,
                    seed,
                    mode,
                    duration_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary["created_at"],
                    summary["score"],
                    summary["raw_score"],
                    summary["stats"]["correct"],
                    summary["stats"]["incorrect"],
                    summary["stats"]["unanswered"],
                    summary["stats"]["attempted"],
                    summary["stats"]["accuracy"],
                    summary["stats"]["average_response_time_seconds"],
                    json.dumps(summary["settings"]),
                    summary["seed"],
                    summary["mode_label"],
                    summary["duration_seconds"],
                ),
            )
            run_id = int(cursor.lastrowid)
            question_rows = [
                question.to_storage_row(
                    run_id=run_id,
                    mode_label=summary["mode_label"],
                    question_index=index + 1,
                )
                for index, question in enumerate(session.questions)
                if question.presented_at is not None
            ]
            if question_rows:
                connection.executemany(
                    """
                    INSERT INTO run_questions (
                        run_id,
                        mode,
                        question_index,
                        prompt,
                        correct_answer,
                        submitted_answer,
                        correct_flag,
                        result_label,
                        response_time_ms,
                        base_operation,
                        used_decimal,
                        used_missing_variable,
                        left_value,
                        right_value,
                        result_value,
                        answer_role,
                        family_label,
                        difficulty_tag,
                        difficulty_at_question,
                        selected_option_index,
                        correct_option_index,
                        operation_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    question_rows,
                )
            connection.commit()

    def leaderboard(self, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    id,
                    created_at,
                    score,
                    raw_score,
                    correct,
                    incorrect,
                    unanswered,
                    attempted,
                    accuracy,
                    average_response_time,
                    mode,
                    duration_seconds
                FROM runs
                ORDER BY score DESC, accuracy DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "timestamp": row["created_at"],
                "score": row["score"],
                "raw_score": row["raw_score"],
                "correct": row["correct"],
                "incorrect": row["incorrect"],
                "unanswered": row["unanswered"],
                "attempted": row["attempted"],
                "accuracy": round(row["accuracy"], 4),
                "accuracy_percent": round(row["accuracy"] * 100, 2),
                "average_response_time_seconds": round(row["average_response_time"], 3),
                "mode": normalize_mode_name(row["mode"]),
                "duration_seconds": row["duration_seconds"],
            }
            for row in rows
        ]

    def list_saved_run_ids(self) -> list[int]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM runs
                ORDER BY id ASC
                """
            ).fetchall()
        return [int(row[0]) for row in rows]

    def list_saved_questions(self, run_id: int) -> list[dict[str, Any]]:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    id,
                    run_id,
                    mode,
                    question_index,
                    prompt,
                    correct_answer,
                    submitted_answer,
                    correct_flag,
                    result_label,
                    response_time_ms,
                    base_operation,
                    used_decimal,
                    used_missing_variable,
                    left_value,
                    right_value,
                    result_value,
                    answer_role,
                    family_label,
                    difficulty_tag,
                    difficulty_at_question,
                    selected_option_index,
                    correct_option_index,
                    operation_type
                FROM run_questions
                WHERE run_id = ?
                ORDER BY question_index ASC
                """,
                (run_id,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "mode": normalize_mode_name(row["mode"]),
                "question_index": row["question_index"],
                "prompt": row["prompt"],
                "correct_answer": row["correct_answer"],
                "submitted_answer": row["submitted_answer"],
                "correct_flag": row["correct_flag"],
                "result_label": row["result_label"],
                "response_time_ms": row["response_time_ms"],
                "base_operation": row["base_operation"] or row["operation_type"],
                "used_decimal": bool(row["used_decimal"]),
                "used_missing_variable": bool(row["used_missing_variable"]),
                "left": row["left_value"],
                "right": row["right_value"],
                "result": row["result_value"],
                "answer_role": row["answer_role"],
                "family_label": row["family_label"],
                "difficulty_tag": row["difficulty_tag"],
                "difficulty_at_question": row["difficulty_at_question"],
                "selected_option_index": row["selected_option_index"],
                "correct_option_index": row["correct_option_index"],
            }
            for row in rows
        ]

    def build_saved_question_features(self, run_id: int) -> list[dict[str, Any]]:
        return extract_saved_question_feature_rows(self.list_saved_questions(run_id))

    def build_saved_question_core_features(self, run_id: int) -> list[dict[str, Any]]:
        return extract_core_saved_question_feature_rows(self.list_saved_questions(run_id))

    _ALLOWED_TABLE_NAMES = frozenset({"runs", "run_questions"})

    def _ensure_column(self, connection: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
        if table_name not in self._ALLOWED_TABLE_NAMES:
            raise ValueError(f"Disallowed table name: {table_name!r}")
        if not column_name.isidentifier():
            raise ValueError(f"Disallowed column name: {column_name!r}")
        columns = {
            row[1]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")

    def _normalize_mode_values(self, connection: sqlite3.Connection) -> None:
        for stored_value, normalized_value in (
            ("assessment", "Interview Mode"),
            ("training", "Practice Mode"),
            ("zetamac", "Zetamac Mode"),
        ):
            connection.execute("UPDATE runs SET mode = ? WHERE mode = ?", (normalized_value, stored_value))
            connection.execute("UPDATE run_questions SET mode = ? WHERE mode = ?", (normalized_value, stored_value))

    def _backfill_base_operation(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            UPDATE run_questions
            SET base_operation = operation_type
            WHERE (base_operation IS NULL OR base_operation = '')
              AND operation_type IS NOT NULL
            """
        )
