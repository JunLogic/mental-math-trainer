from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.models.game import GameSession, normalize_mode_name


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
                    response_time_ms INTEGER,
                    operation_type TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                )
                """
            )
            self._ensure_column(connection, "runs", "mode", "TEXT NOT NULL DEFAULT 'assessment'")
            self._ensure_column(connection, "runs", "duration_seconds", "INTEGER NOT NULL DEFAULT 480")
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
                (
                    run_id,
                    summary["mode_label"],
                    index + 1,
                    question.prompt,
                    question.correct_answer,
                    question.submitted_answer,
                    1 if question.result == "correct" else 0,
                    question.response_time_ms,
                    question.base_operation,
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
                        response_time_ms,
                        operation_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def _ensure_column(self, connection: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
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
