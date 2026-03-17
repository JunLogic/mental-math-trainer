from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.game import BaseOperation, QuestionRecord
from app.services.config import GenerationSettings

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
            question = self._generate_question()
            duplicate_attempts = 0
            while duplicate_attempts < 24 and question.prompt in seen_prompts:
                question = self._generate_question()
                duplicate_attempts += 1
            seen_prompts.add(question.prompt)
            questions.append(question)

        return questions

    def _generate_question(self) -> QuestionRecord:
        if self.settings.mode == "zetamac":
            return self._generate_zetamac_question()

        base_operation = self.rng.choices(
            population=list(self.operation_weights.keys()),
            weights=list(self.operation_weights.values()),
            k=1,
        )[0]
        used_decimal = self.rng.random() < self.normalized_settings["decimal_probability"]
        used_missing_variable = self.rng.random() < self.normalized_settings["missing_variable_probability"]

        operand_set = self._generate_operands(base_operation, used_decimal)
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
            },
        )

    def _generate_zetamac_question(self) -> QuestionRecord:
        zetamac_settings = self.settings.zetamac_settings
        enabled_operations = [
            operation
            for operation, enabled in zetamac_settings["operations"].items()
            if enabled
        ]
        base_operation = self.rng.choice(enabled_operations)
        left, right, result = self._generate_zetamac_operands(base_operation, zetamac_settings["ranges"][base_operation])
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
            },
        )

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

    def _generate_operands(self, base_operation: BaseOperation, used_decimal: bool) -> OperandSet:
        if base_operation == "addition":
            return self._generate_addition(used_decimal)
        if base_operation == "subtraction":
            return self._generate_subtraction(used_decimal)
        if base_operation == "multiplication":
            return self._generate_multiplication(used_decimal)
        return self._generate_division(used_decimal)

    def _generate_addition(self, used_decimal: bool) -> OperandSet:
        profile = self.settings.difficulty_profile["addition"]
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
        for _ in range(40):
            left = Decimal(self._random_int(profile["integer_left"]))
            right = Decimal(self._random_int(profile["integer_right"]))
            carries = self._has_integer_carry(left, right)
            if wants_carry == carries:
                tag = "carry" if carries else "clean"
                return OperandSet(left=left, right=right, result=left + right, difficulty_tag=tag)
        return OperandSet(left=left, right=right, result=left + right, difficulty_tag="mixed")

    def _generate_subtraction(self, used_decimal: bool) -> OperandSet:
        profile = self.settings.difficulty_profile["subtraction"]
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
        for _ in range(40):
            right = Decimal(self._random_int(profile["integer_right"]))
            result = Decimal(self._random_int(profile["integer_result"]))
            left = right + result
            has_borrow = self._has_integer_borrow(left, right)
            if wants_borrow == has_borrow:
                tag = "borrow" if has_borrow else "clean"
                return OperandSet(left=left, right=right, result=result, difficulty_tag=tag)
        return OperandSet(left=left, right=right, result=result, difficulty_tag="mixed")

    def _generate_multiplication(self, used_decimal: bool) -> OperandSet:
        profile = self.settings.difficulty_profile["multiplication"]
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

        left = Decimal(self._random_int(profile["integer_left"]))
        right = Decimal(self._random_int(profile["integer_right"]))
        if self.rng.random() < profile["large_factor_bias"]:
            if left < 10 and right < 10:
                if self.rng.random() < 0.5:
                    left = Decimal(max(10, int(left) + self.rng.randint(2, 6)))
                else:
                    right = Decimal(max(10, int(right) + self.rng.randint(2, 6)))
            tag = "larger_factors"
        else:
            tag = "standard_factors"
        return OperandSet(left=left, right=right, result=left * right, difficulty_tag=tag)

    def _generate_division(self, used_decimal: bool) -> OperandSet:
        profile = self.settings.difficulty_profile["division"]
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

        right = Decimal(self._random_int(profile["integer_divisor"]))
        result = Decimal(self._random_int(profile["integer_result"]))
        if self.rng.random() < 0.68:
            if right < 12:
                right += Decimal(self.rng.randint(2, 6))
            if result < 10:
                result += Decimal(self.rng.randint(2, 5))
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

    def _has_integer_carry(self, left: Decimal, right: Decimal) -> bool:
        left_digits = [int(digit) for digit in str(int(left))[::-1]]
        right_digits = [int(digit) for digit in str(int(right))[::-1]]
        carry = 0
        for index in range(max(len(left_digits), len(right_digits))):
            left_digit = left_digits[index] if index < len(left_digits) else 0
            right_digit = right_digits[index] if index < len(right_digits) else 0
            carry = 1 if left_digit + right_digit + carry >= 10 else 0
            if carry:
                return True
        return False

    def _has_integer_borrow(self, left: Decimal, right: Decimal) -> bool:
        left_digits = [int(digit) for digit in str(int(left))[::-1]]
        right_digits = [int(digit) for digit in str(int(right))[::-1]]
        borrow = 0
        for index in range(max(len(left_digits), len(right_digits))):
            left_digit = left_digits[index] if index < len(left_digits) else 0
            right_digit = right_digits[index] if index < len(right_digits) else 0
            if left_digit - borrow < right_digit:
                return True
            borrow = 0
        return False

    def _tenths_digit(self, value: Decimal) -> int:
        return int((value * 10) % 10)
