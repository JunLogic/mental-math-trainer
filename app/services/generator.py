from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.game import BaseOperation, QuestionRecord
from app.services.config import GenerationSettings, clamp, difficulty_profile_for_scalar

OPERATION_SYMBOLS: dict[BaseOperation, str] = {
    "addition": "+",
    "subtraction": "-",
    "multiplication": "x",
    "division": "/",
}
TENTH = Decimal("0.1")


@dataclass
class OperandSet:
    left: Decimal
    right: Decimal
    result: Decimal
    difficulty_tag: str


@dataclass
class QuestionContext:
    left: Decimal
    right: Decimal
    result: Decimal
    prompt: str
    correct_answer: Decimal
    answer_role: str


def format_number(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def to_decimal_from_tenths(value: int) -> Decimal:
    return Decimal(value) * TENTH


def decimal_from_text(value: str) -> Decimal:
    return Decimal(value)


class QuestionGenerator:
    def __init__(self, settings: GenerationSettings, seed: int) -> None:
        self.settings = settings
        self.seed = seed
        self.rng = random.Random(seed)
        self.normalized_settings = settings.normalized()
        self.operation_weights: dict[BaseOperation, float] = {
            "addition": settings.addition_weight,
            "subtraction": settings.subtraction_weight,
            "multiplication": settings.multiplication_weight,
            "division": settings.division_weight,
        }

    def generate_run(self) -> list[QuestionRecord]:
        questions: list[QuestionRecord] = []
        seen_prompts: set[str] = set()

        while len(questions) < self.settings.max_questions:
            question = self.generate_question(seen_prompts=seen_prompts)
            questions.append(question)

        return questions

    def generate_question(
        self,
        adaptive_difficulty: float | None = None,
        seen_prompts: set[str] | None = None,
    ) -> QuestionRecord:
        question = self._generate_question(adaptive_difficulty=adaptive_difficulty)
        if seen_prompts is None:
            return question

        duplicate_attempts = 0
        while duplicate_attempts < 24 and question.prompt in seen_prompts:
            question = self._generate_question(adaptive_difficulty=adaptive_difficulty)
            duplicate_attempts += 1
        seen_prompts.add(question.prompt)
        return question

    def _generate_question(self, adaptive_difficulty: float | None = None) -> QuestionRecord:
        if self.settings.mode == "zetamac":
            return self._generate_zetamac_question(adaptive_difficulty=adaptive_difficulty)

        generation_context = self._resolve_generation_context(adaptive_difficulty)

        base_operation = self.rng.choices(
            population=list(generation_context["operation_weights"].keys()),
            weights=list(generation_context["operation_weights"].values()),
            k=1,
        )[0]
        used_decimal = self.rng.random() < generation_context["decimal_probability"]
        used_missing_variable = self.rng.random() < generation_context["missing_variable_probability"]

        operand_set = self._generate_operands(
            base_operation,
            used_decimal,
            difficulty_profile=generation_context["difficulty_profile"],
        )
        context = self._build_question_context(
            base_operation=base_operation,
            left=operand_set.left,
            right=operand_set.right,
            result=operand_set.result,
            used_missing_variable=used_missing_variable,
        )
        options, correct_option_index = self._build_options(
            correct_answer=context.correct_answer,
            left=operand_set.left,
            right=operand_set.right,
            result=operand_set.result,
            base_operation=base_operation,
            used_decimal=used_decimal,
            answer_role=context.answer_role,
        )
        family_label = self._family_label(base_operation, used_decimal, used_missing_variable)

        return QuestionRecord(
            prompt=context.prompt,
            options=options,
            correct_option_index=correct_option_index,
            correct_answer=format_number(context.correct_answer),
            base_operation=base_operation,
            used_decimal=used_decimal,
            used_missing_variable=used_missing_variable,
            metadata={
                "left": format_number(operand_set.left),
                "right": format_number(operand_set.right),
                "result": format_number(operand_set.result),
                "answer_role": context.answer_role,
                "difficulty_tag": operand_set.difficulty_tag,
                "family_label": family_label,
                "preset_name": self.settings.preset_name,
                "difficulty_at_question": round(adaptive_difficulty, 2) if adaptive_difficulty is not None else None,
            },
        )

    def _generate_zetamac_question(self, adaptive_difficulty: float | None = None) -> QuestionRecord:
        zetamac_settings = self.settings.zetamac_settings
        enabled_operations = [
            operation
            for operation, enabled in zetamac_settings["operations"].items()
            if enabled
        ]
        base_operation = self.rng.choice(enabled_operations)
        operation_ranges = zetamac_settings["ranges"][base_operation]
        effective_ranges = (
            self._adaptive_zetamac_ranges(operation_ranges, adaptive_difficulty)
            if adaptive_difficulty is not None
            else operation_ranges
        )
        left, right, result = self._generate_zetamac_operands(base_operation, effective_ranges)
        prompt = f"{format_number(left)} {OPERATION_SYMBOLS[base_operation]} {format_number(right)}"
        family_label = f"zetamac {base_operation}"
        return QuestionRecord(
            prompt=prompt,
            options=[],
            correct_option_index=0,
            correct_answer=format_number(result),
            base_operation=base_operation,
            used_decimal=False,
            used_missing_variable=False,
            metadata={
                "left": format_number(left),
                "right": format_number(right),
                "result": format_number(result),
                "answer_role": "result",
                "difficulty_tag": "range_drill",
                "family_label": family_label,
                "preset_name": "zetamac",
                "difficulty_at_question": round(adaptive_difficulty, 2) if adaptive_difficulty is not None else None,
            },
        )

    def _resolve_generation_context(self, adaptive_difficulty: float | None) -> dict[str, Any]:
        if adaptive_difficulty is None:
            return {
                "operation_weights": self.operation_weights,
                "decimal_probability": self.normalized_settings["decimal_probability"],
                "missing_variable_probability": self.normalized_settings["missing_variable_probability"],
                "difficulty_profile": self.settings.difficulty_profile,
            }

        adaptive_difficulty = clamp(float(adaptive_difficulty), 0.0, 100.0)
        difficulty_shift = (adaptive_difficulty - 40.0) / 60.0
        operation_weights = dict(self.operation_weights)
        if self.settings.mode == "assessment":
            operation_weights["addition"] *= clamp(1.0 - (0.24 * difficulty_shift), 0.62, 1.15)
            operation_weights["subtraction"] *= clamp(1.0 - (0.12 * difficulty_shift), 0.72, 1.12)
            operation_weights["multiplication"] *= clamp(1.0 + (0.32 * difficulty_shift), 0.82, 1.65)
            operation_weights["division"] *= clamp(1.0 + (0.24 * difficulty_shift), 0.82, 1.5)
            decimal_minimum, decimal_maximum = 0.12, 0.68
            missing_minimum, missing_maximum = 0.05, 0.42
        else:
            operation_weights["addition"] *= clamp(1.0 - (0.18 * difficulty_shift), 0.75, 1.2)
            operation_weights["subtraction"] *= clamp(1.0 - (0.08 * difficulty_shift), 0.8, 1.15)
            operation_weights["multiplication"] *= clamp(1.0 + (0.14 * difficulty_shift), 0.8, 1.3)
            operation_weights["division"] *= clamp(1.0 + (0.12 * difficulty_shift), 0.8, 1.3)
            decimal_minimum, decimal_maximum = 0.08, 0.62
            missing_minimum, missing_maximum = 0.03, 0.38
        return {
            "operation_weights": operation_weights,
            "decimal_probability": clamp(
                self.normalized_settings["decimal_probability"] + (0.18 * difficulty_shift),
                decimal_minimum,
                decimal_maximum,
            ),
            "missing_variable_probability": clamp(
                self.normalized_settings["missing_variable_probability"] + (0.14 * difficulty_shift),
                missing_minimum,
                missing_maximum,
            ),
            "difficulty_profile": difficulty_profile_for_scalar(adaptive_difficulty),
        }

    def _adaptive_zetamac_ranges(self, ranges: dict[str, int], adaptive_difficulty: float) -> dict[str, int]:
        span_scale = clamp(0.35 + ((adaptive_difficulty / 100.0) * 0.65), 0.25, 1.0)
        effective_ranges: dict[str, int] = {}
        for side in ("left", "right"):
            minimum = ranges[f"{side}_min"]
            maximum = ranges[f"{side}_max"]
            span = max(0, maximum - minimum)
            adjusted_maximum = minimum + int(round(span * span_scale))
            effective_ranges[f"{side}_min"] = minimum
            effective_ranges[f"{side}_max"] = min(maximum, adjusted_maximum)
        return effective_ranges

    def _generate_zetamac_operands(
        self,
        base_operation: BaseOperation,
        ranges: dict[str, int],
    ) -> tuple[Decimal, Decimal, Decimal]:
        if base_operation == "addition":
            left = Decimal(self.rng.randint(ranges["left_min"], ranges["left_max"]))
            right = Decimal(self.rng.randint(ranges["right_min"], ranges["right_max"]))
            return left, right, left + right

        if base_operation == "subtraction":
            answer = Decimal(self.rng.randint(ranges["left_min"], ranges["left_max"]))
            right = Decimal(self.rng.randint(ranges["right_min"], ranges["right_max"]))
            left = answer + right
            return left, right, answer

        if base_operation == "multiplication":
            left = Decimal(self.rng.randint(ranges["left_min"], ranges["left_max"]))
            right = Decimal(self.rng.randint(ranges["right_min"], ranges["right_max"]))
            return left, right, left * right

        answer = Decimal(self.rng.randint(ranges["left_min"], ranges["left_max"]))
        right = Decimal(self.rng.randint(ranges["right_min"], ranges["right_max"]))
        left = answer * right
        return left, right, answer

    def _generate_operands(
        self,
        base_operation: BaseOperation,
        used_decimal: bool,
        difficulty_profile: dict[str, Any] | None = None,
    ) -> OperandSet:
        profile = difficulty_profile or self.settings.difficulty_profile
        if base_operation == "addition":
            return self._generate_addition(used_decimal, profile)
        if base_operation == "subtraction":
            return self._generate_subtraction(used_decimal, profile)
        if base_operation == "multiplication":
            return self._generate_multiplication(used_decimal, profile)
        return self._generate_division(used_decimal, profile)

    def _generate_addition(self, used_decimal: bool, difficulty_profile: dict[str, Any]) -> OperandSet:
        profile = difficulty_profile["addition"]
        if used_decimal:
            wants_carry = self.rng.random() < profile["decimal_carry_bias"]
            for _ in range(40):
                left = self._random_tenth(profile["decimal_left_tenths"])
                right = self._random_tenth(profile["decimal_right_tenths"])
                tenths_carry = self._tenths_digit(left) + self._tenths_digit(right) >= 10
                if wants_carry == tenths_carry:
                    tag = "decimal_tenths_carry" if tenths_carry else "decimal_clean"
                    return OperandSet(left=left, right=right, result=left + right, difficulty_tag=tag)
            return OperandSet(left=left, right=right, result=left + right, difficulty_tag="decimal_mixed")

        wants_carry = self.rng.random() < profile["carry_bias"]
        wants_multi_carry = wants_carry and self.rng.random() < float(profile.get("multi_carry_bias", 0.0))
        for _ in range(64):
            left = Decimal(self._random_int(profile["integer_left"]))
            right = Decimal(self._random_int(profile["integer_right"]))
            carry_count = self._count_integer_carries(left, right)
            carries = carry_count > 0
            if wants_multi_carry and carry_count < 2:
                continue
            if wants_carry == carries:
                if carry_count >= 2:
                    tag = "multi_carry"
                else:
                    tag = "carry" if carries else "clean"
                return OperandSet(left=left, right=right, result=left + right, difficulty_tag=tag)
        return OperandSet(left=left, right=right, result=left + right, difficulty_tag="mixed")

    def _generate_subtraction(self, used_decimal: bool, difficulty_profile: dict[str, Any]) -> OperandSet:
        profile = difficulty_profile["subtraction"]
        if used_decimal:
            wants_borrow = self.rng.random() < profile["decimal_borrow_bias"]
            for _ in range(40):
                right = self._random_tenth(profile["decimal_right_tenths"])
                result = self._random_tenth(profile["decimal_result_tenths"])
                left = right + result
                has_borrow = self._tenths_digit(left) < self._tenths_digit(right)
                if wants_borrow == has_borrow:
                    tag = "decimal_borrow" if has_borrow else "decimal_clean"
                    return OperandSet(left=left, right=right, result=result, difficulty_tag=tag)
            return OperandSet(left=left, right=right, result=result, difficulty_tag="decimal_mixed")

        wants_borrow = self.rng.random() < profile["borrow_bias"]
        wants_chain_borrow = wants_borrow and self.rng.random() < float(profile.get("chain_borrow_bias", 0.0))
        wants_across_zero = wants_borrow and self.rng.random() < float(profile.get("across_zero_bias", 0.0))

        if wants_across_zero:
            across_zero_candidate = self._generate_across_zero_subtraction(profile)
            if across_zero_candidate is not None:
                return across_zero_candidate

        for _ in range(72):
            right = Decimal(self._random_int(profile["integer_right"]))
            result = Decimal(self._random_int(profile["integer_result"]))
            left = right + result
            borrow_details = self._integer_borrow_details(left, right)
            has_borrow = borrow_details["borrow_count"] > 0
            if wants_chain_borrow and borrow_details["borrow_count"] < 2:
                continue
            if wants_across_zero and not borrow_details["borrow_across_zero"]:
                continue
            if wants_borrow == has_borrow:
                if borrow_details["borrow_across_zero"]:
                    tag = "across_zero_borrow"
                elif borrow_details["borrow_count"] >= 2:
                    tag = "chain_borrow"
                else:
                    tag = "borrow" if has_borrow else "clean"
                return OperandSet(left=left, right=right, result=result, difficulty_tag=tag)
        return OperandSet(left=left, right=right, result=result, difficulty_tag="mixed")

    def _generate_multiplication(self, used_decimal: bool, difficulty_profile: dict[str, Any]) -> OperandSet:
        profile = difficulty_profile["multiplication"]
        if used_decimal:
            if self.rng.random() < profile["pair_bias"]:
                left_text, right_text = self.rng.choice(profile["decimal_pair_choices"])
                left = decimal_from_text(left_text)
                right = decimal_from_text(right_text)
                return OperandSet(
                    left=left,
                    right=right,
                    result=left * right,
                    difficulty_tag="decimal_pair",
                )

            integer_factor = Decimal(self._random_int(profile["decimal_integer_factor"]))
            decimal_factor = decimal_from_text(self.rng.choice(profile["decimal_factor_choices"]))
            if self.rng.random() < 0.5:
                left, right = integer_factor, decimal_factor
            else:
                left, right = decimal_factor, integer_factor
            return OperandSet(left=left, right=right, result=left * right, difficulty_tag="decimal_factor")

        integer_pair_choices = profile.get("integer_pair_choices", [])
        if integer_pair_choices and self.rng.random() < float(profile.get("hard_pair_bias", 0.0)):
            left_value, right_value = self.rng.choice(integer_pair_choices)
            left = Decimal(left_value)
            right = Decimal(right_value)
            return OperandSet(left=left, right=right, result=left * right, difficulty_tag="two_digit_pair")

        left = Decimal(self._random_int(profile["integer_left"]))
        right = Decimal(self._random_int(profile["integer_right"]))
        if self.rng.random() < float(profile.get("two_digit_pair_bias", 0.0)):
            left = Decimal(max(10, int(left)))
            right = Decimal(max(10, int(right)))
        if self.rng.random() < profile["large_factor_bias"]:
            if left < 10 and right < 10:
                if self.rng.random() < 0.5:
                    left = Decimal(max(10, int(left) + self.rng.randint(2, 6)))
                else:
                    right = Decimal(max(10, int(right) + self.rng.randint(2, 6)))
            tag = "two_digit_multiplication" if left >= 10 and right >= 10 else "larger_factors"
        else:
            tag = "standard_factors"
        return OperandSet(left=left, right=right, result=left * right, difficulty_tag=tag)

    def _generate_division(self, used_decimal: bool, difficulty_profile: dict[str, Any]) -> OperandSet:
        profile = difficulty_profile["division"]
        if used_decimal:
            patterns = ["decimal_pair", "decimal_divisor", "decimal_quotient"]
            weights = [profile["pair_bias"], (1 - profile["pair_bias"]) / 2, (1 - profile["pair_bias"]) / 2]
            pattern = self.rng.choices(patterns, weights=weights, k=1)[0]
            if pattern == "decimal_pair":
                left_text, right_text, result_text = self.rng.choice(profile["decimal_pair_choices"])
                return OperandSet(
                    left=decimal_from_text(left_text),
                    right=decimal_from_text(right_text),
                    result=decimal_from_text(result_text),
                    difficulty_tag="decimal_pair",
                )
            if pattern == "decimal_divisor":
                right = decimal_from_text(self.rng.choice(profile["decimal_divisor_choices"]))
                result = Decimal(self._random_int(profile["decimal_int_result"]))
                return OperandSet(left=right * result, right=right, result=result, difficulty_tag="decimal_divisor")

            right = Decimal(self._random_int(profile["integer_divisor"]))
            result = decimal_from_text(self.rng.choice(profile["decimal_result_choices"]))
            return OperandSet(left=right * result, right=right, result=result, difficulty_tag="decimal_quotient")

        integer_pair_choices = profile.get("integer_pair_choices", [])
        if integer_pair_choices and self.rng.random() < float(profile.get("integer_pair_bias", 0.0)):
            left_text, right_text, result_text = self.rng.choice(integer_pair_choices)
            return OperandSet(
                left=decimal_from_text(left_text),
                right=decimal_from_text(right_text),
                result=decimal_from_text(result_text),
                difficulty_tag="integer_pair",
            )

        right = Decimal(self._random_int(profile["integer_divisor"]))
        result = Decimal(self._random_int(profile["integer_result"]))
        if self.rng.random() < 0.68:
            if right < 14:
                right += Decimal(self.rng.randint(3, 8))
            if result < 12:
                result += Decimal(self.rng.randint(3, 7))
        return OperandSet(left=right * result, right=right, result=result, difficulty_tag="larger_division")

    def _build_question_context(
        self,
        base_operation: BaseOperation,
        left: Decimal,
        right: Decimal,
        result: Decimal,
        used_missing_variable: bool,
    ) -> QuestionContext:
        if not used_missing_variable:
            prompt = f"{format_number(left)} {OPERATION_SYMBOLS[base_operation]} {format_number(right)}"
            return QuestionContext(
                left=left,
                right=right,
                result=result,
                prompt=prompt,
                correct_answer=result,
                answer_role="result",
            )

        builder = {
            "addition": self._addition_missing_prompt,
            "subtraction": self._subtraction_missing_prompt,
            "multiplication": self._multiplication_missing_prompt,
            "division": self._division_missing_prompt,
        }[base_operation]
        return builder(left=left, right=right, result=result)

    def _addition_missing_prompt(self, left: Decimal, right: Decimal, result: Decimal) -> QuestionContext:
        prompt, correct_answer, answer_role = self._choose_missing_variant(
            direct_variants=[
                (f"? + {format_number(right)} = {format_number(result)}", left, "left"),
                (f"{format_number(left)} + ? = {format_number(result)}", right, "right"),
            ],
            reversed_variants=[
                (f"{format_number(result)} = ? + {format_number(right)}", left, "left"),
                (f"{format_number(result)} = {format_number(left)} + ?", right, "right"),
            ],
        )
        return QuestionContext(left=left, right=right, result=result, prompt=prompt, correct_answer=correct_answer, answer_role=answer_role)

    def _subtraction_missing_prompt(self, left: Decimal, right: Decimal, result: Decimal) -> QuestionContext:
        prompt, correct_answer, answer_role = self._choose_missing_variant(
            direct_variants=[
                (f"? - {format_number(right)} = {format_number(result)}", left, "left"),
                (f"{format_number(left)} - ? = {format_number(result)}", right, "right"),
            ],
            reversed_variants=[
                (f"{format_number(result)} = ? - {format_number(right)}", left, "left"),
                (f"{format_number(result)} = {format_number(left)} - ?", right, "right"),
            ],
        )
        return QuestionContext(left=left, right=right, result=result, prompt=prompt, correct_answer=correct_answer, answer_role=answer_role)

    def _multiplication_missing_prompt(self, left: Decimal, right: Decimal, result: Decimal) -> QuestionContext:
        prompt, correct_answer, answer_role = self._choose_missing_variant(
            direct_variants=[
                (f"? x {format_number(right)} = {format_number(result)}", left, "left"),
                (f"{format_number(left)} x ? = {format_number(result)}", right, "right"),
            ],
            reversed_variants=[
                (f"{format_number(result)} = ? x {format_number(right)}", left, "left"),
                (f"{format_number(result)} = {format_number(left)} x ?", right, "right"),
            ],
        )
        return QuestionContext(left=left, right=right, result=result, prompt=prompt, correct_answer=correct_answer, answer_role=answer_role)

    def _division_missing_prompt(self, left: Decimal, right: Decimal, result: Decimal) -> QuestionContext:
        prompt, correct_answer, answer_role = self._choose_missing_variant(
            direct_variants=[
                (f"? / {format_number(right)} = {format_number(result)}", left, "left"),
                (f"{format_number(left)} / ? = {format_number(result)}", right, "right"),
            ],
            reversed_variants=[
                (f"{format_number(result)} = ? / {format_number(right)}", left, "left"),
                (f"{format_number(result)} = {format_number(left)} / ?", right, "right"),
            ],
        )
        return QuestionContext(left=left, right=right, result=result, prompt=prompt, correct_answer=correct_answer, answer_role=answer_role)

    def _choose_missing_variant(
        self,
        direct_variants: list[tuple[str, Decimal, str]],
        reversed_variants: list[tuple[str, Decimal, str]],
    ) -> tuple[str, Decimal, str]:
        if self.rng.random() < 0.82:
            return self.rng.choice(direct_variants)
        return self.rng.choice(reversed_variants)

    def _build_options(
        self,
        correct_answer: Decimal,
        left: Decimal,
        right: Decimal,
        result: Decimal,
        base_operation: BaseOperation,
        used_decimal: bool,
        answer_role: str,
    ) -> tuple[list[str], int]:
        step = Decimal("0.1") if used_decimal else Decimal(1)
        medium_step = Decimal("0.2") if used_decimal else Decimal(2)
        wide_step = Decimal("0.5") if used_decimal else (Decimal(10) if abs(correct_answer) >= 20 else Decimal(4))

        candidate_values: list[Decimal] = [
            correct_answer + step,
            correct_answer - step,
            correct_answer + medium_step,
            correct_answer - medium_step,
            correct_answer + wide_step,
            correct_answer - wide_step,
        ]

        if answer_role == "result":
            if base_operation == "addition":
                candidate_values.extend([abs(left - right), result + wide_step, result - wide_step])
            elif base_operation == "subtraction":
                candidate_values.extend([left + right, result + wide_step, result - medium_step])
            elif base_operation == "multiplication":
                candidate_values.extend([left + right, result + left, result - right])
            else:
                candidate_values.extend([result + medium_step, result - medium_step, right, left / right if right else left])
        else:
            known_operand = right if answer_role == "left" else left
            other_operand = left if answer_role == "left" else right
            candidate_values.extend(
                [
                    known_operand,
                    other_operand,
                    correct_answer + medium_step,
                    correct_answer - medium_step,
                ]
            )
            if base_operation == "addition":
                candidate_values.extend([result + known_operand, abs(result - known_operand) + step])
            elif base_operation == "subtraction":
                candidate_values.extend([result + known_operand, abs(result - known_operand)])
            elif base_operation == "multiplication":
                candidate_values.extend([known_operand + step, correct_answer + wide_step])
            else:
                candidate_values.extend([known_operand + step, correct_answer + wide_step])

        cleaned_candidates: list[str] = []
        unique_values: list[Decimal] = []
        correct_text = format_number(correct_answer)
        for candidate in candidate_values:
            if correct_answer > 0 and candidate <= 0:
                continue
            formatted = format_number(candidate)
            if formatted == correct_text or formatted in cleaned_candidates:
                continue
            cleaned_candidates.append(formatted)
            unique_values.append(candidate)

        adjustment = 1
        while len(unique_values) < 3:
            for direction in (1, -1):
                candidate = correct_answer + (step * adjustment * direction)
                if correct_answer > 0 and candidate <= 0:
                    continue
                formatted = format_number(candidate)
                if formatted != correct_text and formatted not in cleaned_candidates:
                    cleaned_candidates.append(formatted)
                    unique_values.append(candidate)
                if len(unique_values) >= 3:
                    break
            adjustment += 1

        option_text = cleaned_candidates[:3] + [correct_text]
        self.rng.shuffle(option_text)
        correct_option_index = option_text.index(correct_text)
        return option_text, correct_option_index

    def _family_label(self, base_operation: BaseOperation, used_decimal: bool, used_missing_variable: bool) -> str:
        parts = ["decimal" if used_decimal else "integer", base_operation]
        if used_missing_variable:
            parts.append("missing")
        return " ".join(parts)

    def _random_int(self, range_values: list[int]) -> int:
        return self.rng.randint(range_values[0], range_values[1])

    def _random_tenth(self, range_values: list[int]) -> Decimal:
        return to_decimal_from_tenths(self._random_int(range_values))

    def _count_integer_carries(self, left: Decimal, right: Decimal) -> int:
        left_digits = [int(digit) for digit in str(int(left))[::-1]]
        right_digits = [int(digit) for digit in str(int(right))[::-1]]
        carry = 0
        carry_count = 0
        for index in range(max(len(left_digits), len(right_digits))):
            left_digit = left_digits[index] if index < len(left_digits) else 0
            right_digit = right_digits[index] if index < len(right_digits) else 0
            carry = 1 if left_digit + right_digit + carry >= 10 else 0
            if carry:
                carry_count += 1
        return carry_count

    def _has_integer_carry(self, left: Decimal, right: Decimal) -> bool:
        return self._count_integer_carries(left, right) > 0

    def _integer_borrow_details(self, left: Decimal, right: Decimal) -> dict[str, int | bool]:
        left_digits = [int(digit) for digit in str(int(left))[::-1]]
        right_digits = [int(digit) for digit in str(int(right))[::-1]]
        borrow = 0
        borrow_count = 0
        current_chain = 0
        longest_chain = 0
        borrow_across_zero = False
        for index in range(max(len(left_digits), len(right_digits))):
            left_digit = left_digits[index] if index < len(left_digits) else 0
            right_digit = right_digits[index] if index < len(right_digits) else 0
            effective_left = left_digit - borrow
            next_borrow = effective_left < right_digit
            if next_borrow:
                borrow_count += 1
                current_chain += 1
                longest_chain = max(longest_chain, current_chain)
                if left_digit == 0 or effective_left < 0:
                    borrow_across_zero = True
                borrow = 1
            else:
                current_chain = 0
                borrow = 0
        return {
            "borrow_count": borrow_count,
            "borrow_across_zero": borrow_across_zero,
            "longest_chain": longest_chain,
        }

    def _has_integer_borrow(self, left: Decimal, right: Decimal) -> bool:
        return bool(self._integer_borrow_details(left, right)["borrow_count"])

    def _generate_across_zero_subtraction(self, profile: dict[str, Any]) -> OperandSet | None:
        maximum_left = profile["integer_right"][1] + profile["integer_result"][1]
        minimum_right = max(2, profile["integer_right"][0])
        for _ in range(48):
            hundreds_digit = self.rng.randint(1, max(1, min(9, maximum_left // 100 or 1)))
            tens_digit = self.rng.choice([0, 0, 0, 1, 2, 3, 4])
            units_digit = self.rng.randint(1, 9)
            left_value = (hundreds_digit * 100) + (tens_digit * 10) + units_digit
            if left_value > maximum_left or left_value <= minimum_right:
                continue

            upper_right = min(profile["integer_right"][1], left_value - 1)
            if minimum_right > upper_right:
                continue

            for _ in range(24):
                right_value = self.rng.randint(minimum_right, upper_right)
                borrow_details = self._integer_borrow_details(Decimal(left_value), Decimal(right_value))
                result_value = left_value - right_value
                if (
                    borrow_details["borrow_across_zero"]
                    and borrow_details["borrow_count"] >= 2
                    and profile["integer_result"][0] <= result_value <= profile["integer_result"][1]
                ):
                    return OperandSet(
                        left=Decimal(left_value),
                        right=Decimal(right_value),
                        result=Decimal(result_value),
                        difficulty_tag="across_zero_borrow",
                    )
        return None

    def _tenths_digit(self, value: Decimal) -> int:
        return int((value * 10) % 10)
