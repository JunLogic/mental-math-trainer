from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.runtime import resolve_data_dir

DATA_DIR = resolve_data_dir()
DEFAULT_SETTINGS_PATH = DATA_DIR / "question_settings.json"
DEFAULT_PRESET_NAME = "interview_default"
DEFAULT_ZETAMAC_DURATION = 120
ZETAMAC_ALLOWED_DURATIONS = {30, 60, 120, 300, 600}
ADAPTIVE_TARGET_PACE_PRESETS = (2.0, 2.5, 3.0)
ADAPTIVE_MIN_TARGET_PACE = 2.0
ADAPTIVE_MAX_TARGET_PACE = 6.0
DEFAULT_ADAPTIVE_TARGET_PACE = 2.0
DEFAULT_ADAPTIVE_INITIAL_DIFFICULTY = 40.0
PRESET_ALIASES: dict[str, str] = {
    "user_observed": "interview_default",
    "consensus": "interview_balanced",
    "training_easy": "practice_easy",
    "training_hard": "practice_default",
}

EASY_DIFFICULTY: dict[str, Any] = {
    "label": "easy",
    "addition": {
        "integer_left": [18, 94],
        "integer_right": [9, 79],
        "carry_bias": 0.35,
        "decimal_left_tenths": [8, 120],
        "decimal_right_tenths": [4, 95],
        "decimal_carry_bias": 0.45,
    },
    "subtraction": {
        "integer_right": [12, 84],
        "integer_result": [8, 82],
        "borrow_bias": 0.4,
        "decimal_right_tenths": [6, 105],
        "decimal_result_tenths": [4, 95],
        "decimal_borrow_bias": 0.45,
    },
    "multiplication": {
        "integer_left": [4, 12],
        "integer_right": [4, 13],
        "large_factor_bias": 0.2,
        "decimal_integer_factor": [3, 12],
        "decimal_factor_choices": ["0.6", "0.8", "1.2", "1.5", "1.8", "2.4"],
        "decimal_pair_choices": [["1.8", "2.5"], ["2.4", "1.5"], ["0.8", "2.5"]],
        "pair_bias": 0.2,
    },
    "division": {
        "integer_divisor": [3, 12],
        "integer_result": [3, 16],
        "decimal_int_result": [3, 11],
        "decimal_divisor_choices": ["0.6", "0.8", "1.2", "1.5", "1.8", "2.4"],
        "decimal_result_choices": ["1.2", "1.5", "1.8", "2.4", "3.2", "3.5", "4.2", "5.6"],
        "decimal_pair_choices": [
            ["8.4", "1.2", "7"],
            ["7.2", "1.8", "4"],
            ["6.3", "1.5", "4.2"],
            ["9.6", "1.6", "6"],
        ],
        "pair_bias": 0.25,
    },
}

BALANCED_DIFFICULTY: dict[str, Any] = {
    "label": "balanced",
    "addition": {
        "integer_left": [24, 128],
        "integer_right": [14, 102],
        "carry_bias": 0.5,
        "decimal_left_tenths": [12, 148],
        "decimal_right_tenths": [7, 124],
        "decimal_carry_bias": 0.58,
    },
    "subtraction": {
        "integer_right": [18, 108],
        "integer_result": [12, 96],
        "borrow_bias": 0.55,
        "decimal_right_tenths": [12, 130],
        "decimal_result_tenths": [8, 118],
        "decimal_borrow_bias": 0.58,
    },
    "multiplication": {
        "integer_left": [5, 14],
        "integer_right": [6, 16],
        "large_factor_bias": 0.35,
        "decimal_integer_factor": [4, 15],
        "decimal_factor_choices": ["0.7", "0.8", "1.2", "1.4", "1.5", "1.8", "2.4", "2.5"],
        "decimal_pair_choices": [["1.8", "2.5"], ["2.4", "1.5"], ["3.6", "2.5"], ["1.4", "3.5"]],
        "pair_bias": 0.3,
    },
    "division": {
        "integer_divisor": [4, 14],
        "integer_result": [4, 18],
        "decimal_int_result": [4, 12],
        "decimal_divisor_choices": ["0.6", "0.8", "1.2", "1.4", "1.5", "1.8", "2.5"],
        "decimal_result_choices": ["1.2", "1.4", "1.8", "2.4", "3.4", "4.2", "5.6", "6.4"],
        "decimal_pair_choices": [
            ["8.5", "2.5", "3.4"],
            ["12.6", "1.8", "7"],
            ["7.2", "1.2", "6"],
            ["9.6", "1.6", "6"],
            ["14.4", "0.8", "18"],
        ],
        "pair_bias": 0.35,
    },
}

HARD_DIFFICULTY: dict[str, Any] = {
    "label": "harder",
    "addition": {
        "integer_left": [72, 428],
        "integer_right": [34, 286],
        "carry_bias": 0.9,
        "multi_carry_bias": 0.44,
        "decimal_left_tenths": [28, 268],
        "decimal_right_tenths": [18, 218],
        "decimal_carry_bias": 0.86,
    },
    "subtraction": {
        "integer_right": [34, 268],
        "integer_result": [28, 248],
        "borrow_bias": 0.9,
        "chain_borrow_bias": 0.38,
        "across_zero_bias": 0.24,
        "decimal_right_tenths": [22, 208],
        "decimal_result_tenths": [16, 198],
        "decimal_borrow_bias": 0.86,
    },
    "multiplication": {
        "integer_left": [8, 29],
        "integer_right": [9, 31],
        "large_factor_bias": 0.88,
        "two_digit_pair_bias": 0.72,
        "hard_pair_bias": 0.5,
        "integer_pair_choices": [
            [17, 14],
            [18, 16],
            [19, 17],
            [21, 14],
            [22, 13],
            [23, 17],
            [24, 16],
            [24, 18],
            [25, 17],
            [26, 14],
            [27, 16],
            [28, 13],
            [19, 18],
            [21, 17],
            [24, 25],
        ],
        "decimal_integer_factor": [7, 22],
        "decimal_factor_choices": ["0.6", "0.8", "1.2", "1.4", "1.5", "1.8", "2.4", "2.5", "3.5", "3.6", "4.2"],
        "decimal_pair_choices": [
            ["1.8", "2.5"],
            ["2.4", "1.5"],
            ["3.6", "2.5"],
            ["1.4", "3.5"],
            ["2.8", "1.5"],
            ["4.2", "1.5"],
            ["1.25", "2.4"],
        ],
        "pair_bias": 0.48,
    },
    "division": {
        "integer_divisor": [7, 24],
        "integer_result": [8, 26],
        "integer_pair_bias": 0.48,
        "integer_pair_choices": [
            ["252", "14", "18"],
            ["272", "16", "17"],
            ["276", "12", "23"],
            ["286", "13", "22"],
            ["288", "16", "18"],
            ["323", "17", "19"],
            ["336", "14", "24"],
            ["391", "17", "23"],
            ["399", "19", "21"],
            ["408", "17", "24"],
            ["425", "17", "25"],
            ["432", "24", "18"],
        ],
        "decimal_int_result": [6, 16],
        "decimal_divisor_choices": ["0.6", "0.8", "1.2", "1.4", "1.5", "1.8", "2.1", "2.4", "2.5", "3.5"],
        "decimal_result_choices": ["1.2", "1.4", "1.8", "2.4", "3.4", "4.2", "5.6", "6.4", "7.5", "8.4"],
        "decimal_pair_choices": [
            ["8.5", "2.5", "3.4"],
            ["12.6", "1.8", "7"],
            ["7.2", "1.2", "6"],
            ["9.6", "1.6", "6"],
            ["14.4", "0.8", "18"],
            ["18.9", "2.7", "7"],
            ["6.3", "1.5", "4.2"],
            ["10.5", "2.5", "4.2"],
            ["16.8", "2.4", "7"],
            ["14.7", "2.1", "7"],
            ["3.0", "1.25", "2.4"],
        ],
        "pair_bias": 0.52,
    },
}

PRESET_DEFINITIONS: dict[str, dict[str, Any]] = {
    "interview_balanced": {
        "mode": "assessment",
        "weights": {
            "addition_weight": 24,
            "subtraction_weight": 22,
            "multiplication_weight": 18,
            "division_weight": 14,
            "decimal_weight": 24,
            "missing_variable_weight": 12,
        },
        "difficulty_profile": BALANCED_DIFFICULTY,
    },
    "interview_default": {
        "mode": "assessment",
        "weights": {
            "addition_weight": 14,
            "subtraction_weight": 16,
            "multiplication_weight": 22,
            "division_weight": 18,
            "decimal_weight": 42,
            "missing_variable_weight": 28,
        },
        "difficulty_profile": HARD_DIFFICULTY,
    },
    "practice_easy": {
        "mode": "training",
        "weights": {
            "addition_weight": 26,
            "subtraction_weight": 24,
            "multiplication_weight": 18,
            "division_weight": 10,
            "decimal_weight": 16,
            "missing_variable_weight": 10,
        },
        "difficulty_profile": EASY_DIFFICULTY,
    },
    "practice_default": {
        "mode": "training",
        "weights": {
            "addition_weight": 18,
            "subtraction_weight": 18,
            "multiplication_weight": 16,
            "division_weight": 12,
            "decimal_weight": 40,
            "missing_variable_weight": 24,
        },
        "difficulty_profile": HARD_DIFFICULTY,
    },
}

DEFAULT_ZETAMAC_SETTINGS: dict[str, Any] = {
    "duration_seconds": DEFAULT_ZETAMAC_DURATION,
    "allow_negative_answers": False,
    "operations": {
        "addition": True,
        "subtraction": True,
        "multiplication": True,
        "division": True,
    },
    "ranges": {
        "addition": {"left_min": 10, "left_max": 99, "right_min": 10, "right_max": 99},
        "subtraction": {"left_min": 10, "left_max": 99, "right_min": 10, "right_max": 99},
        "multiplication": {"left_min": 2, "left_max": 12, "right_min": 2, "right_max": 12},
        "division": {"left_min": 2, "left_max": 12, "right_min": 2, "right_max": 12},
    },
}


def deep_merge_dicts(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def canonical_preset_name(preset_name: str) -> str:
    return PRESET_ALIASES.get(preset_name, preset_name)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _interpolate_number(low: int | float, high: int | float, t: float) -> int | float:
    interpolated = low + (high - low) * t
    if isinstance(low, int) and isinstance(high, int):
        return int(round(interpolated))
    return round(float(interpolated), 4)


def _interpolate_profile_value(low: Any, high: Any, t: float) -> Any:
    if isinstance(low, dict) and isinstance(high, dict):
        return {
            key: _interpolate_profile_value(low[key], high[key], t)
            for key in low
        }
    if isinstance(low, list) and isinstance(high, list):
        if len(low) == len(high) == 2 and all(isinstance(item, (int, float)) for item in low + high):
            return [_interpolate_number(low[0], high[0], t), _interpolate_number(low[1], high[1], t)]
        return copy.deepcopy(low if t < 0.5 else high)
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        return _interpolate_number(low, high, t)
    return copy.deepcopy(low if t < 0.5 else high)


def difficulty_profile_for_scalar(difficulty: float) -> dict[str, Any]:
    normalized_difficulty = clamp(float(difficulty), 0.0, 100.0)
    if normalized_difficulty <= 50:
        low_profile, high_profile = EASY_DIFFICULTY, BALANCED_DIFFICULTY
        blend = normalized_difficulty / 50
    else:
        low_profile, high_profile = BALANCED_DIFFICULTY, HARD_DIFFICULTY
        blend = (normalized_difficulty - 50) / 50
    return _interpolate_profile_value(low_profile, high_profile, blend)


def estimate_zetamac_question_budget(duration_seconds: int) -> int:
    return max(120, duration_seconds * 3)


def validate_zetamac_settings(raw_settings: dict[str, Any]) -> dict[str, Any]:
    settings = deep_merge_dicts(DEFAULT_ZETAMAC_SETTINGS, raw_settings)
    duration_seconds = int(settings["duration_seconds"])
    if duration_seconds not in ZETAMAC_ALLOWED_DURATIONS:
        raise ValueError("zetamac duration_seconds must be one of 30, 60, 120, 300, or 600.")

    operations = settings.get("operations", {})
    if not any(bool(operations.get(operation)) for operation in ("addition", "subtraction", "multiplication", "division")):
        raise ValueError("At least one Zetamac operation must be enabled.")

    for operation_name in ("addition", "subtraction", "multiplication", "division"):
        operation_ranges = settings["ranges"][operation_name]
        left_min = int(operation_ranges["left_min"])
        left_max = int(operation_ranges["left_max"])
        right_min = int(operation_ranges["right_min"])
        right_max = int(operation_ranges["right_max"])
        if left_min > left_max or right_min > right_max:
            raise ValueError(f"Invalid Zetamac range for {operation_name}.")
        settings["ranges"][operation_name] = {
            "left_min": left_min,
            "left_max": left_max,
            "right_min": right_min,
            "right_max": right_max,
        }

    settings["duration_seconds"] = duration_seconds
    settings["allow_negative_answers"] = bool(settings.get("allow_negative_answers", False))
    return settings


@dataclass
class GenerationSettings:
    preset_name: str = DEFAULT_PRESET_NAME
    mode: str = "assessment"
    addition_weight: float = 18
    subtraction_weight: float = 16
    multiplication_weight: float = 14
    division_weight: float = 12
    decimal_weight: float = 35
    missing_variable_weight: float = 20
    allow_negative_answers: bool = False
    max_questions: int = 80
    duration_seconds: int = 480
    difficulty_profile: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(HARD_DIFFICULTY))
    zetamac_settings: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_ZETAMAC_SETTINGS))
    adaptive_enabled: bool = False
    target_pace_seconds: float = DEFAULT_ADAPTIVE_TARGET_PACE
    initial_difficulty: float = DEFAULT_ADAPTIVE_INITIAL_DIFFICULTY

    def validate(self) -> None:
        weights = [
            self.addition_weight,
            self.subtraction_weight,
            self.multiplication_weight,
            self.division_weight,
            self.decimal_weight,
            self.missing_variable_weight,
        ]
        if any(weight < 0 for weight in weights):
            raise ValueError("Question weights must be non-negative.")

        operation_total = (
            self.addition_weight
            + self.subtraction_weight
            + self.multiplication_weight
            + self.division_weight
        )
        if operation_total <= 0:
            raise ValueError("At least one operation weight must be greater than zero.")

        total_weight = operation_total + self.decimal_weight + self.missing_variable_weight
        if total_weight <= 0:
            raise ValueError("The combined weight total must be greater than zero.")

        if self.mode not in {"assessment", "training", "zetamac"}:
            raise ValueError("mode must be 'assessment', 'training', or 'zetamac'.")
        if self.max_questions <= 0:
            raise ValueError("max_questions must be positive.")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive.")
        if not self.difficulty_profile:
            raise ValueError("difficulty_profile must be provided.")
        self.target_pace_seconds = float(self.target_pace_seconds)
        if not ADAPTIVE_MIN_TARGET_PACE <= self.target_pace_seconds <= ADAPTIVE_MAX_TARGET_PACE:
            raise ValueError(
                f"target_pace_seconds must be between {ADAPTIVE_MIN_TARGET_PACE:.1f} and {ADAPTIVE_MAX_TARGET_PACE:.1f}."
            )
        self.initial_difficulty = clamp(float(self.initial_difficulty), 0.0, 100.0)
        self.adaptive_enabled = bool(self.adaptive_enabled)
        self.zetamac_settings = validate_zetamac_settings(self.zetamac_settings)
        if self.mode == "zetamac":
            self.duration_seconds = self.zetamac_settings["duration_seconds"]
            self.max_questions = estimate_zetamac_question_budget(self.duration_seconds)

    def normalized(self) -> dict[str, Any]:
        self.validate()
        operation_total = (
            self.addition_weight
            + self.subtraction_weight
            + self.multiplication_weight
            + self.division_weight
        )
        total_weight = operation_total + self.decimal_weight + self.missing_variable_weight
        return {
            "addition_probability": self.addition_weight / operation_total,
            "subtraction_probability": self.subtraction_weight / operation_total,
            "multiplication_probability": self.multiplication_weight / operation_total,
            "division_probability": self.division_weight / operation_total,
            "decimal_probability": self.decimal_weight / total_weight,
            "missing_variable_probability": self.missing_variable_weight / total_weight,
        }

    def to_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["normalized"] = self.normalized()
        return values

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "GenerationSettings":
        preset_name = canonical_preset_name(str(values.get("preset_name", DEFAULT_PRESET_NAME)))
        values = dict(values)
        values["preset_name"] = preset_name
        if values.get("mode") == "zetamac" or preset_name == "zetamac":
            base = cls.for_zetamac()
        else:
            base = cls.from_preset(preset_name) if preset_name in PRESET_DEFINITIONS else cls()
        merged: dict[str, Any] = base.to_dict()
        merged.pop("normalized", None)
        merged = deep_merge_dicts(merged, values)
        settings = cls(**merged)
        settings.validate()
        return settings

    @classmethod
    def from_preset(cls, preset_name: str, mode: str | None = None) -> "GenerationSettings":
        preset_name = canonical_preset_name(preset_name)
        if preset_name not in PRESET_DEFINITIONS:
            raise ValueError(f"Unknown preset: {preset_name}")

        preset = PRESET_DEFINITIONS[preset_name]
        settings = cls(
            preset_name=preset_name,
            mode=mode or preset["mode"],
            difficulty_profile=copy.deepcopy(preset["difficulty_profile"]),
            **preset["weights"],
        )
        settings.validate()
        return settings

    @classmethod
    def for_zetamac(cls, overrides: dict[str, Any] | None = None) -> "GenerationSettings":
        settings = cls(
            preset_name="zetamac",
            mode="zetamac",
            duration_seconds=DEFAULT_ZETAMAC_DURATION,
            zetamac_settings=copy.deepcopy(DEFAULT_ZETAMAC_SETTINGS),
        )
        if overrides:
            merged = deep_merge_dicts(settings.to_dict(), overrides)
            merged.pop("normalized", None)
            settings = cls(**merged)
        settings.validate()
        return settings


def available_presets() -> list[str]:
    return list(PRESET_DEFINITIONS.keys())


def load_default_settings() -> GenerationSettings:
    if DEFAULT_SETTINGS_PATH.exists():
        with DEFAULT_SETTINGS_PATH.open("r", encoding="utf-8") as handle:
            raw_values = json.load(handle)
        return GenerationSettings.from_dict(raw_values)
    return GenerationSettings.from_preset(DEFAULT_PRESET_NAME)
