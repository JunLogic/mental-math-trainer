from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Any, Literal

BaseOperation = Literal["addition", "subtraction", "multiplication", "division"]
QuestionResult = Literal["correct", "incorrect", "unanswered"]
MODE_LABELS: dict[str, str] = {
    "assessment": "Interview Mode",
    "training": "Practice Mode",
    "zetamac": "Zetamac Mode",
    "Interview Mode": "Interview Mode",
    "Practice Mode": "Practice Mode",
    "Zetamac Mode": "Zetamac Mode",
}
OPERATION_LABELS: dict[BaseOperation, str] = {
    "addition": "Addition",
    "subtraction": "Subtraction",
    "multiplication": "Multiplication",
    "division": "Division",
}


def normalize_mode_name(mode: str) -> str:
    return MODE_LABELS.get(mode, mode)


def display_operation_name(operation: BaseOperation) -> str:
    return OPERATION_LABELS.get(operation, operation.title())


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
            "difficulty_at_question": self.metadata.get("difficulty_at_question"),
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
            "difficulty_at_question": self.metadata.get("difficulty_at_question"),
            "response_time_seconds": (
                round(self.response_time_ms / 1000, 3) if self.response_time_ms is not None else None
            ),
        }

    def to_storage_row(self, run_id: int, mode_label: str, question_index: int) -> tuple[Any, ...]:
        return (
            run_id,
            mode_label,
            question_index,
            self.prompt,
            self.correct_answer,
            self.submitted_answer,
            1 if self.result == "correct" else 0,
            self.result,
            self.response_time_ms,
            self.base_operation,
            1 if self.used_decimal else 0,
            1 if self.used_missing_variable else 0,
            self.metadata.get("left"),
            self.metadata.get("right"),
            self.metadata.get("result"),
            self.metadata.get("answer_role"),
            self.metadata.get("family_label"),
            self.metadata.get("difficulty_tag"),
            self.metadata.get("difficulty_at_question"),
            self.selected_option,
            self.correct_option_index,
            self.base_operation,
        )


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
    generator: Any | None = None
    seen_prompts: set[str] = field(default_factory=set)
    adaptive_current_difficulty: float | None = None
    adaptive_peak_difficulty: float | None = None
    finished: bool = False
    finalized_at: datetime | None = None
    finish_reason: str | None = None
    leaderboard_saved: bool = False

    @property
    def total_questions(self) -> int:
        return int(self.generation_settings.get("max_questions", len(self.questions)))

    def current_question(self) -> QuestionRecord | None:
        if self.finished or self.current_index >= self.total_questions or self.current_index >= len(self.questions):
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

    def _attempted_response_times_seconds(self) -> list[float]:
        return [
            question.response_time_ms / 1000
            for question in self.questions
            if question.response_time_ms is not None and question.result in {"correct", "incorrect"}
        ]

    def average_response_time_seconds(self) -> float:
        response_times = self._attempted_response_times_seconds()
        if not response_times:
            return 0.0
        return sum(response_times) / len(response_times)

    def median_response_time_seconds(self) -> float:
        response_times = self._attempted_response_times_seconds()
        if not response_times:
            return 0.0
        return float(median(response_times))

    def fastest_response_time_seconds(self) -> float:
        response_times = self._attempted_response_times_seconds()
        if not response_times:
            return 0.0
        return min(response_times)

    def slowest_response_time_seconds(self) -> float:
        response_times = self._attempted_response_times_seconds()
        if not response_times:
            return 0.0
        return max(response_times)

    def operation_mix_used(self) -> str:
        if self.mode == "zetamac":
            operations = self.generation_settings.get("zetamac_settings", {}).get("operations", {})
            enabled = [name for name, enabled in operations.items() if enabled]
            return ", ".join(display_operation_name(name) for name in enabled) if enabled else "None"
        return self.generation_settings.get("preset_name", "-")

    def adaptive_enabled(self) -> bool:
        return bool(self.generation_settings.get("adaptive_enabled", False))

    def question_difficulties(self) -> list[float]:
        difficulties: list[float] = []
        for question in self.shown_questions():
            difficulty = question.metadata.get("difficulty_at_question")
            if difficulty is None:
                continue
            difficulties.append(float(difficulty))
        return difficulties

    def average_difficulty(self) -> float | None:
        difficulties = self.question_difficulties()
        if not difficulties:
            return None
        return sum(difficulties) / len(difficulties)

    def adaptive_summary(self) -> dict[str, Any]:
        if not self.adaptive_enabled():
            return {
                "enabled": False,
                "target_pace_seconds": None,
                "initial_difficulty": None,
                "final_difficulty": None,
                "peak_difficulty": None,
                "average_difficulty": None,
                "achieved_median_pace_seconds": None,
            }

        initial_difficulty = float(self.generation_settings.get("initial_difficulty", 40.0))
        average_difficulty = self.average_difficulty()
        return {
            "enabled": True,
            "target_pace_seconds": float(self.generation_settings.get("target_pace_seconds", 2.0)),
            "initial_difficulty": round(initial_difficulty, 2),
            "final_difficulty": round(float(self.adaptive_current_difficulty or initial_difficulty), 2),
            "peak_difficulty": round(float(self.adaptive_peak_difficulty or initial_difficulty), 2),
            "average_difficulty": round(float(average_difficulty if average_difficulty is not None else initial_difficulty), 2),
            "achieved_median_pace_seconds": round(self.median_response_time_seconds(), 3),
        }

    def diagnostics(self) -> dict[str, Any]:
        shown_questions = self.shown_questions()
        total_shown = len(shown_questions)
        decimal_count = sum(1 for question in shown_questions if question.used_decimal)
        missing_count = sum(1 for question in shown_questions if question.used_missing_variable)
        family_totals: dict[str, dict[str, Any]] = {}
        operation_totals: dict[BaseOperation, dict[str, Any]] = {}

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

            operation_bucket = operation_totals.setdefault(
                question.base_operation,
                {
                    "operation": question.base_operation,
                    "operation_label": display_operation_name(question.base_operation),
                    "shown": 0,
                    "attempted": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "unanswered": 0,
                    "response_times": [],
                },
            )
            operation_bucket["shown"] += 1
            if question.result == "correct":
                operation_bucket["attempted"] += 1
                operation_bucket["correct"] += 1
            elif question.result == "incorrect":
                operation_bucket["attempted"] += 1
                operation_bucket["incorrect"] += 1
            elif question.result == "unanswered":
                operation_bucket["unanswered"] += 1

            if question.response_time_ms is not None and question.result in {"correct", "incorrect"}:
                operation_bucket["response_times"].append(question.response_time_ms / 1000)

        by_family = []
        for family_label in sorted(family_totals):
            bucket = family_totals[family_label]
            response_times = bucket.pop("response_times")
            bucket["average_response_time_seconds"] = (
                round(sum(response_times) / len(response_times), 3) if response_times else 0.0
            )
            by_family.append(bucket)

        by_operation = []
        for operation_name in ("addition", "subtraction", "multiplication", "division"):
            if operation_name not in operation_totals:
                continue
            bucket = operation_totals[operation_name]
            response_times = bucket.pop("response_times")
            accuracy = (bucket["correct"] / bucket["attempted"]) if bucket["attempted"] else 0.0
            bucket["accuracy"] = round(accuracy, 4)
            bucket["accuracy_percent"] = round(accuracy * 100, 2)
            bucket["average_response_time_seconds"] = (
                round(sum(response_times) / len(response_times), 3) if response_times else 0.0
            )
            by_operation.append(bucket)

        return {
            "decimal_questions": decimal_count,
            "decimal_share": round(decimal_count / total_shown, 4) if total_shown else 0.0,
            "decimal_share_percent": round((decimal_count / total_shown) * 100, 2) if total_shown else 0.0,
            "missing_variable_questions": missing_count,
            "missing_variable_share": round(missing_count / total_shown, 4) if total_shown else 0.0,
            "missing_variable_share_percent": round((missing_count / total_shown) * 100, 2) if total_shown else 0.0,
            "by_operation": by_operation,
            "by_family": by_family,
        }

    def summary(self) -> dict[str, Any]:
        adaptive_summary = self.adaptive_summary()
        settings = dict(self.generation_settings)
        settings["adaptive_summary"] = adaptive_summary
        return {
            "session_id": self.session_id,
            "seed": self.seed,
            "mode": self.mode,
            "mode_label": normalize_mode_name(self.mode),
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
                "fastest_response_time_seconds": round(self.fastest_response_time_seconds(), 3),
                "slowest_response_time_seconds": round(self.slowest_response_time_seconds(), 3),
            },
            "adaptive": adaptive_summary,
            "diagnostics": self.diagnostics(),
            "settings": settings,
        }
