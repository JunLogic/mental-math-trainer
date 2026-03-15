from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Any, Literal

BaseOperation = Literal["addition", "subtraction", "multiplication", "division"]
QuestionResult = Literal["correct", "incorrect", "unanswered"]


@dataclass
class QuestionRecord:
    prompt: str
    options: list[str]
    correct_option_index: int
    correct_answer: str
    base_operation: BaseOperation
    used_decimal: bool
    used_missing_variable: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    presented_at: datetime | None = None
    answered_at: datetime | None = None
    selected_option: int | None = None
    submitted_answer: str | None = None
    result: QuestionResult | None = None
    response_time_ms: int | None = None

    def to_public(self, question_number: int, total_questions: int, mode: str) -> dict[str, Any]:
        payload = {
            "question_number": question_number,
            "total_questions": total_questions,
            "prompt": self.prompt,
            "base_operation": self.base_operation,
            "used_decimal": self.used_decimal,
            "used_missing_variable": self.used_missing_variable,
            "family_label": self.metadata.get("family_label"),
            "difficulty_tag": self.metadata.get("difficulty_tag"),
            "input_mode": "multiple_choice" if mode == "training" else "typed",
        }
        payload["options"] = self.options if mode == "training" else []
        return payload

    def to_history_row(self, question_number: int) -> dict[str, Any]:
        selected_value = None
        if self.submitted_answer is not None:
            selected_value = self.submitted_answer
        elif self.selected_option is not None and 0 <= self.selected_option < len(self.options):
            selected_value = self.options[self.selected_option]

        return {
            "question_number": question_number,
            "prompt": self.prompt,
            "selected_option": self.selected_option,
            "selected_value": selected_value,
            "correct_answer": self.correct_answer,
            "result": self.result,
            "family_label": self.metadata.get("family_label"),
            "difficulty_tag": self.metadata.get("difficulty_tag"),
            "used_decimal": self.used_decimal,
            "used_missing_variable": self.used_missing_variable,
            "response_time_seconds": (
                round(self.response_time_ms / 1000, 3) if self.response_time_ms is not None else None
            ),
        }


@dataclass
class GameSession:
    session_id: str
    seed: int
    mode: str
    created_at: datetime
    started_at: datetime
    expires_at: datetime
    current_index: int
    score: int
    raw_score: int
    correct: int
    incorrect: int
    unanswered: int
    attempted: int
    questions: list[QuestionRecord]
    generation_settings: dict[str, Any]
    finished: bool = False
    finalized_at: datetime | None = None
    finish_reason: str | None = None
    leaderboard_saved: bool = False

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    def current_question(self) -> QuestionRecord | None:
        if self.finished or self.current_index >= self.total_questions:
            return None
        return self.questions[self.current_index]

    def questions_shown(self) -> int:
        return sum(1 for question in self.questions if question.presented_at is not None)

    def shown_questions(self) -> list[QuestionRecord]:
        return [question for question in self.questions if question.presented_at is not None]

    def accuracy(self) -> float:
        if self.attempted == 0:
            return 0.0
        return self.correct / self.attempted

    def average_response_time_seconds(self) -> float:
        response_times = [
            question.response_time_ms / 1000
            for question in self.questions
            if question.response_time_ms is not None and question.result in {"correct", "incorrect"}
        ]
        if not response_times:
            return 0.0
        return sum(response_times) / len(response_times)

    def median_response_time_seconds(self) -> float:
        response_times = [
            question.response_time_ms / 1000
            for question in self.questions
            if question.response_time_ms is not None and question.result in {"correct", "incorrect"}
        ]
        if not response_times:
            return 0.0
        return float(median(response_times))

    def operation_mix_used(self) -> str:
        if self.mode == "zetamac":
            operations = self.generation_settings.get("zetamac_settings", {}).get("operations", {})
            enabled = [name for name, enabled in operations.items() if enabled]
            return ", ".join(enabled) if enabled else "none"
        return self.generation_settings.get("preset_name", "-")

    def diagnostics(self) -> dict[str, Any]:
        shown_questions = self.shown_questions()
        total_shown = len(shown_questions)
        decimal_count = sum(1 for question in shown_questions if question.used_decimal)
        missing_count = sum(1 for question in shown_questions if question.used_missing_variable)
        family_totals: dict[str, dict[str, Any]] = {}

        for question in shown_questions:
            family_label = str(question.metadata.get("family_label") or question.base_operation)
            bucket = family_totals.setdefault(
                family_label,
                {
                    "family_label": family_label,
                    "shown": 0,
                    "attempted": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "unanswered": 0,
                    "score": 0,
                    "response_times": [],
                },
            )
            bucket["shown"] += 1
            if question.result == "correct":
                bucket["attempted"] += 1
                bucket["correct"] += 1
                bucket["score"] += 1
            elif question.result == "incorrect":
                bucket["attempted"] += 1
                bucket["incorrect"] += 1
                bucket["score"] -= 1
            elif question.result == "unanswered":
                bucket["unanswered"] += 1

            if question.response_time_ms is not None and question.result in {"correct", "incorrect"}:
                bucket["response_times"].append(question.response_time_ms / 1000)

        by_family = []
        for family_label in sorted(family_totals):
            bucket = family_totals[family_label]
            response_times = bucket.pop("response_times")
            bucket["average_response_time_seconds"] = (
                round(sum(response_times) / len(response_times), 3) if response_times else 0.0
            )
            by_family.append(bucket)

        return {
            "decimal_questions": decimal_count,
            "decimal_share": round(decimal_count / total_shown, 4) if total_shown else 0.0,
            "decimal_share_percent": round((decimal_count / total_shown) * 100, 2) if total_shown else 0.0,
            "missing_variable_questions": missing_count,
            "missing_variable_share": round(missing_count / total_shown, 4) if total_shown else 0.0,
            "missing_variable_share_percent": round((missing_count / total_shown) * 100, 2) if total_shown else 0.0,
            "by_family": by_family,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "seed": self.seed,
            "mode": self.mode,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "finished": self.finished,
            "finish_reason": self.finish_reason,
            "duration_seconds": self.generation_settings.get("duration_seconds", 0),
            "operation_mix_used": self.operation_mix_used(),
            "total_questions": self.total_questions,
            "current_index": self.current_index,
            "score": self.score,
            "raw_score": self.raw_score,
            "stats": {
                "questions_shown": self.questions_shown(),
                "attempted": self.attempted,
                "correct": self.correct,
                "incorrect": self.incorrect,
                "unanswered": self.unanswered,
                "accuracy": round(self.accuracy(), 4),
                "accuracy_percent": round(self.accuracy() * 100, 2),
                "average_response_time_seconds": round(self.average_response_time_seconds(), 3),
                "median_response_time_seconds": round(self.median_response_time_seconds(), 3),
            },
            "diagnostics": self.diagnostics(),
            "settings": self.generation_settings,
        }
