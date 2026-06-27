from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from fractions import Fraction
from typing import Any, Iterable, Mapping

FEATURE_VERSION = "v1"
TRUST_TIERS = ("core_structural", "derived_sensitive", "heuristic_shortcut")
NEAR_10_DISTANCE = Decimal("2")
NEAR_100_DISTANCE = Decimal("10")
SMALL_DIFFERENCE_THRESHOLD = Decimal("5")
CLOSE_OPERANDS_THRESHOLD = Decimal("3")
SMALL_INTEGER_QUOTIENT_THRESHOLD = 12
EXTRACTED_METADATA_FIELDS: tuple[str, ...] = (
    "feature_version",
    "saved_question_id",
    "run_id",
    "mode",
    "question_index",
    "operation",
    "used_decimal",
    "used_missing_variable",
    "answer_role",
    "family_label",
    "difficulty_tag",
    "difficulty_at_question",
    "result_label",
    "response_time_ms",
    "parse_succeeded",
    "a_value_normalized",
    "b_value_normalized",
    "result_value_normalized",
    "a_decimal_places",
    "b_decimal_places",
    "result_decimal_places",
    "a_is_integer",
    "b_is_integer",
    "result_is_integer",
)

FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "identity": (
        "feature_version",
        "operation",
        "used_decimal",
        "used_missing_variable",
        "answer_role",
        "result_label",
        "response_time_ms",
        "parse_succeeded",
        "a_value_normalized",
        "b_value_normalized",
        "result_value_normalized",
        "a_decimal_places",
        "b_decimal_places",
        "result_decimal_places",
        "a_is_integer",
        "b_is_integer",
        "result_is_integer",
        "family_label",
        "difficulty_tag",
        "difficulty_at_question",
    ),
    "magnitude": (
        "max_operand",
        "min_operand",
        "sum_operands",
        "product_operands",
        "abs_difference_operands",
        "num_digits_a",
        "num_digits_b",
        "num_digits_result",
        "is_single_digit",
        "is_two_digit",
        "is_mixed_digits",
    ),
    "ties": (
        "is_tie",
        "is_double_number_addition",
        "is_square_multiplication",
    ),
    "carry_borrow": (
        "requires_carry",
        "num_carries",
        "carry_in_units",
        "carry_in_tens",
        "carry_creates_new_digit",
        "requires_borrow",
        "num_borrows",
        "borrow_in_units",
        "borrow_in_tens",
        "borrow_across_zero",
        "long_borrow_chain_length",
        "borrow_changes_leading_digit",
    ),
    "place_value": (
        "crosses_10",
        "crosses_100",
        "crosses_1000",
        "result_is_round_10",
        "result_is_round_100",
        "units_sum_to_10",
        "tens_sum_to_10",
        "within_decade",
        "across_decade",
    ),
    "special_operands": (
        "has_zero_operand",
        "has_one_operand",
        "has_two_operand",
        "has_five_operand",
        "has_ten_operand",
        "has_eleven_operand",
        "has_power_of_ten_operand",
        "operand_is_one_less_than_power_of_ten",
        "operand_is_one_more_than_power_of_ten",
    ),
    "parity": (
        "a_even",
        "b_even",
        "both_even",
        "both_odd",
        "mixed_parity",
        "result_even",
    ),
    "base_proximity": (
        "distance_a_to_10",
        "distance_b_to_10",
        "distance_a_to_100",
        "distance_b_to_100",
        "a_near_10",
        "b_near_10",
        "a_near_100",
        "b_near_100",
        "complements_to_10_available",
        "complements_to_100_available",
    ),
    "digit_patterns": (
        "shared_tens_digit",
        "shared_units_digit",
        "repeated_digit_present",
        "all_digits_distinct",
        "contains_zero_inside",
        "digit_sum_a",
        "digit_sum_b",
        "digit_sum_result",
    ),
    "addition": (
        "addition_units_sum",
        "addition_tens_sum",
        "addition_crosses_decade",
        "addition_crosses_century",
        "addition_complement_to_10",
        "addition_complement_to_100",
        "addition_near_doubles",
        "addition_exact_double",
    ),
    "subtraction": (
        "sub_borrow_across_zero",
        "sub_longest_borrow_chain",
        "sub_crosses_decade",
        "sub_crosses_century",
        "sub_difference_small",
        "sub_difference_is_1",
        "sub_difference_is_10",
        "sub_complement_to_10",
        "sub_complement_to_100",
        "sub_close_operands",
        "sub_contains_internal_zero",
        "sub_leading_digit_changes",
        "sub_negative_result",
    ),
    "multiplication": (
        "mult_is_tie",
        "mult_one_digit_by_one_digit",
        "mult_one_digit_by_two_digit",
        "mult_two_digit_by_two_digit",
        "mult_has_zero",
        "mult_has_one",
        "mult_has_two",
        "mult_has_five",
        "mult_has_ten",
        "mult_has_eleven",
        "mult_has_nine",
        "mult_has_twenty_five",
        "mult_even_factor_present",
        "mult_both_even",
        "mult_both_odd",
        "mult_units_product_ge_10",
        "mult_num_partial_products",
        "mult_num_partial_products_with_carry",
        "mult_can_double_and_halve",
        "mult_near_10",
        "mult_near_100",
        "mult_result_trailing_zero_count",
    ),
    "division": (
        "div_exact",
        "div_by_1",
        "div_by_2",
        "div_by_5",
        "div_by_10",
        "div_by_11",
        "div_by_25",
        "quotient_is_integer",
        "quotient_is_small_integer",
        "division_result_terminating_decimal",
    ),
    "shortcuts": (
        "can_double_and_halve",
        "can_use_times_9_as_times_10_minus_1",
        "can_use_times_5_as_half_times_10",
        "can_use_times_25_as_quarter_times_100",
        "can_use_complement_subtraction",
        "can_use_fact_family",
        "can_use_known_square",
        "can_use_near_square",
    ),
}

ALL_EXTRACTED_FEATURES: tuple[str, ...] = EXTRACTED_METADATA_FIELDS + tuple(
    feature_name
    for group_features in FEATURE_GROUPS.values()
    for feature_name in group_features
)

CORE_STRUCTURAL_FEATURES: frozenset[str] = frozenset(
    {
        "feature_version",
        "saved_question_id",
        "run_id",
        "mode",
        "question_index",
        "operation",
        "used_decimal",
        "used_missing_variable",
        "answer_role",
        "result_label",
        "response_time_ms",
        "parse_succeeded",
        "a_value_normalized",
        "b_value_normalized",
        "result_value_normalized",
        "a_decimal_places",
        "b_decimal_places",
        "result_decimal_places",
        "a_is_integer",
        "b_is_integer",
        "result_is_integer",
        "max_operand",
        "min_operand",
        "sum_operands",
        "product_operands",
        "abs_difference_operands",
        "is_tie",
        "is_double_number_addition",
        "is_square_multiplication",
        "requires_carry",
        "num_carries",
        "carry_in_units",
        "carry_in_tens",
        "carry_creates_new_digit",
        "requires_borrow",
        "num_borrows",
        "borrow_in_units",
        "borrow_in_tens",
        "borrow_across_zero",
        "long_borrow_chain_length",
        "borrow_changes_leading_digit",
        "result_is_round_10",
        "result_is_round_100",
        "has_zero_operand",
        "has_one_operand",
        "has_two_operand",
        "has_five_operand",
        "has_ten_operand",
        "has_eleven_operand",
        "has_power_of_ten_operand",
        "a_even",
        "b_even",
        "both_even",
        "both_odd",
        "mixed_parity",
        "result_even",
        "distance_a_to_10",
        "distance_b_to_10",
        "distance_a_to_100",
        "distance_b_to_100",
        "addition_units_sum",
        "addition_tens_sum",
        "addition_crosses_decade",
        "addition_crosses_century",
        "addition_complement_to_10",
        "addition_complement_to_100",
        "addition_exact_double",
        "sub_crosses_decade",
        "sub_crosses_century",
        "sub_difference_is_1",
        "sub_difference_is_10",
        "sub_negative_result",
        "mult_is_tie",
        "mult_one_digit_by_one_digit",
        "mult_one_digit_by_two_digit",
        "mult_two_digit_by_two_digit",
        "mult_has_zero",
        "mult_has_one",
        "mult_has_two",
        "mult_has_five",
        "mult_has_ten",
        "mult_has_eleven",
        "mult_has_nine",
        "mult_has_twenty_five",
        "mult_even_factor_present",
        "mult_both_even",
        "mult_both_odd",
        "mult_units_product_ge_10",
        "mult_result_trailing_zero_count",
        "div_exact",
        "div_by_1",
        "div_by_2",
        "div_by_5",
        "div_by_10",
        "div_by_11",
        "div_by_25",
        "quotient_is_integer",
        "division_result_terminating_decimal",
    }
)

# These stay available in the full extractor, but are intentionally excluded
# from the default modelling-safe core path because they are strategy-like or
# rely on coarse proxies rather than direct arithmetic invariants.
HEURISTIC_SHORTCUT_FEATURES: frozenset[str] = frozenset(
    {
        "complements_to_10_available",
        "complements_to_100_available",
        "mult_num_partial_products_with_carry",
        "mult_can_double_and_halve",
        "can_double_and_halve",
        "can_use_times_9_as_times_10_minus_1",
        "can_use_times_5_as_half_times_10",
        "can_use_times_25_as_quarter_times_100",
        "can_use_complement_subtraction",
        "can_use_fact_family",
        "can_use_known_square",
        "can_use_near_square",
    }
)

DERIVED_SENSITIVE_FEATURES: frozenset[str] = frozenset(
    set(ALL_EXTRACTED_FEATURES) - CORE_STRUCTURAL_FEATURES - HEURISTIC_SHORTCUT_FEATURES
)

FEATURE_TRUST_TIERS: dict[str, str] = {
    **{feature_name: "core_structural" for feature_name in CORE_STRUCTURAL_FEATURES},
    **{feature_name: "derived_sensitive" for feature_name in DERIVED_SENSITIVE_FEATURES},
    **{feature_name: "heuristic_shortcut" for feature_name in HEURISTIC_SHORTCUT_FEATURES},
}

if set(FEATURE_TRUST_TIERS) != set(ALL_EXTRACTED_FEATURES):
    raise RuntimeError("Feature trust-tier coverage is incomplete.")

for left_tier, right_tier, left_features, right_features in (
    ("core_structural", "heuristic_shortcut", CORE_STRUCTURAL_FEATURES, HEURISTIC_SHORTCUT_FEATURES),
    ("core_structural", "derived_sensitive", CORE_STRUCTURAL_FEATURES, DERIVED_SENSITIVE_FEATURES),
    ("derived_sensitive", "heuristic_shortcut", DERIVED_SENSITIVE_FEATURES, HEURISTIC_SHORTCUT_FEATURES),
):
    overlap = left_features & right_features
    if overlap:
        raise RuntimeError(f"Feature trust tiers overlap between {left_tier} and {right_tier}: {sorted(overlap)}")

FEATURE_MANIFEST: dict[str, Any] = {
    "version": FEATURE_VERSION,
    "source": "saved_question_rows",
    "trust_tiers": list(TRUST_TIERS),
    "null_convention": {
        "not_applicable": None,
        "parse_failed": None,
        "meaningful_false": False,
    },
    "feature_groups": {group: list(features) for group, features in FEATURE_GROUPS.items()},
    "feature_trust_tiers": FEATURE_TRUST_TIERS,
    "features_by_trust_tier": {
        "core_structural": sorted(CORE_STRUCTURAL_FEATURES),
        "derived_sensitive": sorted(DERIVED_SENSITIVE_FEATURES),
        "heuristic_shortcut": sorted(HEURISTIC_SHORTCUT_FEATURES),
    },
    "default_model_export": "core_structural",
}


@dataclass(frozen=True)
class ParsedValue:
    raw_text: str | None
    value: Decimal | None
    normalized: str | None
    decimal_places: int | None
    is_integer: bool | None
    integer_value: int | None
    integer_digits: str | None
    digit_characters: str | None


@dataclass(frozen=True)
class ParsedAttemptRow:
    row: Mapping[str, Any]
    operation: str | None
    used_decimal: bool
    used_missing_variable: bool
    answer_role: str | None
    family_label: str | None
    difficulty_tag: str | None
    difficulty_at_question: float | None
    result_label: str | None
    response_time_ms: int | None
    a: ParsedValue
    b: ParsedValue
    result: ParsedValue
    parse_succeeded: bool


def feature_manifest() -> dict[str, Any]:
    return FEATURE_MANIFEST


def feature_names_for_tier(trust_tier: str) -> list[str]:
    if trust_tier not in TRUST_TIERS:
        raise ValueError(f"Unsupported trust tier: {trust_tier}")
    return sorted(
        feature_name
        for feature_name, feature_tier in FEATURE_TRUST_TIERS.items()
        if feature_tier == trust_tier
    )


def core_feature_names() -> list[str]:
    return feature_names_for_tier("core_structural")


def extract_saved_question_features(row: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _parse_attempt_row(row)
    features = {
        "feature_version": FEATURE_VERSION,
        "saved_question_id": _row_value(row, "id"),
        "run_id": _row_value(row, "run_id"),
        "mode": _row_value(row, "mode"),
        "question_index": _row_value(row, "question_index"),
        "operation": parsed.operation,
        "used_decimal": parsed.used_decimal,
        "used_missing_variable": parsed.used_missing_variable,
        "answer_role": parsed.answer_role,
        "family_label": parsed.family_label,
        "difficulty_tag": parsed.difficulty_tag,
        "difficulty_at_question": parsed.difficulty_at_question,
        "result_label": parsed.result_label,
        "response_time_ms": parsed.response_time_ms,
        "parse_succeeded": parsed.parse_succeeded,
        "a_value_normalized": parsed.a.normalized,
        "b_value_normalized": parsed.b.normalized,
        "result_value_normalized": parsed.result.normalized,
        "a_decimal_places": parsed.a.decimal_places,
        "b_decimal_places": parsed.b.decimal_places,
        "result_decimal_places": parsed.result.decimal_places,
        "a_is_integer": parsed.a.is_integer,
        "b_is_integer": parsed.b.is_integer,
        "result_is_integer": parsed.result.is_integer,
    }
    features.update(_magnitude_features(parsed))
    features.update(_tie_features(parsed))
    features.update(_carry_borrow_features(parsed))
    features.update(_place_value_features(parsed))
    features.update(_special_operand_features(parsed))
    features.update(_parity_features(parsed))
    features.update(_base_proximity_features(parsed))
    features.update(_digit_pattern_features(parsed))
    features.update(_addition_features(parsed))
    features.update(_subtraction_features(parsed))
    features.update(_multiplication_features(parsed))
    features.update(_division_features(parsed))
    features.update(_shortcut_features(parsed))
    return features


def extract_saved_question_feature_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [extract_saved_question_features(row) for row in rows]


def extract_core_saved_question_features(row: Mapping[str, Any]) -> dict[str, Any]:
    return _select_feature_subset(
        extract_saved_question_features(row),
        allowed_tiers={"core_structural"},
    )


def extract_core_saved_question_feature_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [extract_core_saved_question_features(row) for row in rows]


def _parse_attempt_row(row: Mapping[str, Any]) -> ParsedAttemptRow:
    operation = _row_value(row, "base_operation", "operation_type")
    used_decimal = bool(_row_value(row, "used_decimal", default=False))
    used_missing_variable = bool(_row_value(row, "used_missing_variable", default=False))
    difficulty_at_question = _optional_float(_row_value(row, "difficulty_at_question"))
    response_time_ms = _optional_int(_row_value(row, "response_time_ms"))
    parsed = ParsedAttemptRow(
        row=row,
        operation=operation,
        used_decimal=used_decimal,
        used_missing_variable=used_missing_variable,
        answer_role=_row_value(row, "answer_role"),
        family_label=_row_value(row, "family_label"),
        difficulty_tag=_row_value(row, "difficulty_tag"),
        difficulty_at_question=difficulty_at_question,
        result_label=_row_value(row, "result_label"),
        response_time_ms=response_time_ms,
        a=_parse_value(_row_value(row, "left", "left_value")),
        b=_parse_value(_row_value(row, "right", "right_value")),
        result=_parse_value(_row_value(row, "result", "result_value")),
        parse_succeeded=False,
    )
    parse_succeeded = all(
        value.value is not None
        for value in (parsed.a, parsed.b, parsed.result)
    )
    return ParsedAttemptRow(
        row=parsed.row,
        operation=parsed.operation,
        used_decimal=parsed.used_decimal,
        used_missing_variable=parsed.used_missing_variable,
        answer_role=parsed.answer_role,
        family_label=parsed.family_label,
        difficulty_tag=parsed.difficulty_tag,
        difficulty_at_question=parsed.difficulty_at_question,
        result_label=parsed.result_label,
        response_time_ms=parsed.response_time_ms,
        a=parsed.a,
        b=parsed.b,
        result=parsed.result,
        parse_succeeded=parse_succeeded,
    )


def _parse_value(raw_value: Any) -> ParsedValue:
    if raw_value is None:
        return ParsedValue(None, None, None, None, None, None, None, None)

    text = str(raw_value).strip()
    if not text:
        return ParsedValue(text, None, None, None, None, None, None, None)

    try:
        value = Decimal(text)
    except InvalidOperation:
        return ParsedValue(text, None, None, None, None, None, None, None)

    normalized = _normalize_decimal(value)
    exponent = value.normalize().as_tuple().exponent
    decimal_places = max(0, -exponent)
    is_integer = value == value.to_integral_value()
    integer_value = int(value) if is_integer else None
    integer_digits = str(abs(integer_value)) if integer_value is not None else None
    digit_characters = "".join(character for character in normalized if character.isdigit())
    return ParsedValue(
        raw_text=text,
        value=value,
        normalized=normalized,
        decimal_places=decimal_places,
        is_integer=is_integer,
        integer_value=integer_value,
        integer_digits=integer_digits,
        digit_characters=digit_characters or None,
    )


def _magnitude_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["magnitude"])
    if not parsed.parse_succeeded:
        return features

    abs_operands = [abs(parsed.a.value), abs(parsed.b.value)]
    num_digits_a = _integer_digit_count(parsed.a)
    num_digits_b = _integer_digit_count(parsed.b)
    num_digits_result = _integer_digit_count(parsed.result)
    features.update(
        {
            "max_operand": _numeric_value(max(abs_operands)),
            "min_operand": _numeric_value(min(abs_operands)),
            "sum_operands": _numeric_value(parsed.a.value + parsed.b.value),
            "product_operands": _numeric_value(parsed.a.value * parsed.b.value),
            "abs_difference_operands": _numeric_value(abs(parsed.a.value - parsed.b.value)),
            "num_digits_a": num_digits_a,
            "num_digits_b": num_digits_b,
            "num_digits_result": num_digits_result,
            "is_single_digit": _both_digit_length(parsed, 1),
            "is_two_digit": _both_digit_length(parsed, 2),
            "is_mixed_digits": (
                num_digits_a != num_digits_b
                if num_digits_a is not None and num_digits_b is not None
                else None
            ),
        }
    )
    return features


def _tie_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["ties"])
    if not parsed.parse_succeeded:
        return features

    is_tie = parsed.a.value == parsed.b.value
    features.update(
        {
            "is_tie": is_tie,
            "is_double_number_addition": parsed.operation == "addition" and is_tie,
            "is_square_multiplication": parsed.operation == "multiplication" and is_tie,
        }
    )
    return features


def _carry_borrow_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["carry_borrow"])
    addition_ready = _integer_binary_operation(parsed, "addition")
    subtraction_ready = _integer_binary_operation(parsed, "subtraction")

    if addition_ready:
        carry_details = _addition_carry_details(parsed.a.integer_value, parsed.b.integer_value)
        features.update(carry_details)
        features.update(
            {
                "requires_borrow": None,
                "num_borrows": None,
                "borrow_in_units": None,
                "borrow_in_tens": None,
                "borrow_across_zero": None,
                "long_borrow_chain_length": None,
                "borrow_changes_leading_digit": None,
            }
        )
    elif subtraction_ready:
        borrow_details = _subtraction_borrow_details(
            parsed.a.integer_value,
            parsed.b.integer_value,
            parsed.result.integer_value,
        )
        features.update(borrow_details)
        features.update(
            {
                "requires_carry": None,
                "num_carries": None,
                "carry_in_units": None,
                "carry_in_tens": None,
                "carry_creates_new_digit": None,
            }
        )
    return features


def _place_value_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["place_value"])
    if not parsed.parse_succeeded or not _all_integers(parsed.a, parsed.b, parsed.result):
        return features

    a = abs(parsed.a.integer_value)
    b = abs(parsed.b.integer_value)
    result = abs(parsed.result.integer_value)
    features.update(
        {
            "crosses_10": _crosses_threshold(parsed, 10),
            "crosses_100": _crosses_threshold(parsed, 100),
            "crosses_1000": _crosses_threshold(parsed, 1000),
            "result_is_round_10": result % 10 == 0,
            "result_is_round_100": result % 100 == 0,
            "units_sum_to_10": (a % 10) + (b % 10) == 10,
            "tens_sum_to_10": ((a // 10) % 10) + ((b // 10) % 10) == 10,
            "within_decade": a // 10 == b // 10,
            "across_decade": a // 10 != b // 10,
        }
    )
    return features


def _special_operand_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["special_operands"])
    if not parsed.parse_succeeded:
        return features

    operands = [parsed.a.value, parsed.b.value]
    features.update(
        {
            "has_zero_operand": any(value == 0 for value in operands),
            "has_one_operand": any(value == 1 for value in operands),
            "has_two_operand": any(value == 2 for value in operands),
            "has_five_operand": any(value == 5 for value in operands),
            "has_ten_operand": any(value == 10 for value in operands),
            "has_eleven_operand": any(value == 11 for value in operands),
            "has_power_of_ten_operand": any(_is_power_of_ten(value) for value in operands),
            "operand_is_one_less_than_power_of_ten": any(_is_offset_from_power_of_ten(value, -1) for value in operands),
            "operand_is_one_more_than_power_of_ten": any(_is_offset_from_power_of_ten(value, 1) for value in operands),
        }
    )
    return features


def _parity_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["parity"])
    if not parsed.parse_succeeded or not _all_integers(parsed.a, parsed.b, parsed.result):
        return features

    a_even = parsed.a.integer_value % 2 == 0
    b_even = parsed.b.integer_value % 2 == 0
    result_even = parsed.result.integer_value % 2 == 0
    features.update(
        {
            "a_even": a_even,
            "b_even": b_even,
            "both_even": a_even and b_even,
            "both_odd": not a_even and not b_even,
            "mixed_parity": a_even != b_even,
            "result_even": result_even,
        }
    )
    return features


def _base_proximity_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["base_proximity"])
    if not parsed.parse_succeeded:
        return features

    distance_a_to_10 = abs(parsed.a.value - Decimal(10))
    distance_b_to_10 = abs(parsed.b.value - Decimal(10))
    distance_a_to_100 = abs(parsed.a.value - Decimal(100))
    distance_b_to_100 = abs(parsed.b.value - Decimal(100))
    features.update(
        {
            "distance_a_to_10": _numeric_value(distance_a_to_10),
            "distance_b_to_10": _numeric_value(distance_b_to_10),
            "distance_a_to_100": _numeric_value(distance_a_to_100),
            "distance_b_to_100": _numeric_value(distance_b_to_100),
            "a_near_10": distance_a_to_10 <= NEAR_10_DISTANCE,
            "b_near_10": distance_b_to_10 <= NEAR_10_DISTANCE,
            "a_near_100": distance_a_to_100 <= NEAR_100_DISTANCE,
            "b_near_100": distance_b_to_100 <= NEAR_100_DISTANCE,
            "complements_to_10_available": _pair_sums_to_target(parsed, 10),
            "complements_to_100_available": _pair_sums_to_target(parsed, 100),
        }
    )
    return features


def _digit_pattern_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["digit_patterns"])
    if not parsed.parse_succeeded:
        return features

    combined_digits = "".join(
        value.digit_characters or ""
        for value in (parsed.a, parsed.b, parsed.result)
    )
    features.update(
        {
            "shared_tens_digit": _shared_place_digit(parsed.a, parsed.b, place=1),
            "shared_units_digit": _shared_place_digit(parsed.a, parsed.b, place=0),
            "repeated_digit_present": (
                len(set(combined_digits)) != len(combined_digits)
                if combined_digits
                else None
            ),
            "all_digits_distinct": (
                len(set(combined_digits)) == len(combined_digits)
                if combined_digits
                else None
            ),
            "contains_zero_inside": _contains_zero_inside(parsed),
            "digit_sum_a": _digit_sum(parsed.a),
            "digit_sum_b": _digit_sum(parsed.b),
            "digit_sum_result": _digit_sum(parsed.result),
        }
    )
    return features


def _addition_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["addition"])
    if not parsed.parse_succeeded or parsed.operation != "addition":
        return features

    features.update(
        {
            "addition_near_doubles": abs(parsed.a.value - parsed.b.value) == 1,
            "addition_exact_double": parsed.a.value == parsed.b.value,
        }
    )
    if not _all_integers(parsed.a, parsed.b, parsed.result):
        return features

    a = abs(parsed.a.integer_value)
    b = abs(parsed.b.integer_value)
    features.update(
        {
            "addition_units_sum": (a % 10) + (b % 10),
            "addition_tens_sum": ((a // 10) % 10) + ((b // 10) % 10),
            "addition_crosses_decade": (a % 10) + (b % 10) >= 10,
            "addition_crosses_century": (a % 100) + (b % 100) >= 100,
            "addition_complement_to_10": parsed.a.value + parsed.b.value == 10,
            "addition_complement_to_100": parsed.a.value + parsed.b.value == 100,
        }
    )
    return features


def _subtraction_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["subtraction"])
    if not parsed.parse_succeeded or parsed.operation != "subtraction":
        return features

    features["sub_negative_result"] = parsed.result.value < 0
    if not _all_integers(parsed.a, parsed.b, parsed.result):
        return features

    borrow_details = _subtraction_borrow_details(
        parsed.a.integer_value,
        parsed.b.integer_value,
        parsed.result.integer_value,
    )
    features.update(
        {
            "sub_borrow_across_zero": borrow_details["borrow_across_zero"],
            "sub_longest_borrow_chain": borrow_details["long_borrow_chain_length"],
            "sub_crosses_decade": parsed.a.integer_value // 10 != parsed.result.integer_value // 10,
            "sub_crosses_century": parsed.a.integer_value // 100 != parsed.result.integer_value // 100,
            "sub_difference_small": abs(parsed.result.value) <= SMALL_DIFFERENCE_THRESHOLD,
            "sub_difference_is_1": abs(parsed.result.value) == 1,
            "sub_difference_is_10": abs(parsed.result.value) == 10,
            "sub_complement_to_10": parsed.b.value + parsed.result.value == 10,
            "sub_complement_to_100": parsed.b.value + parsed.result.value == 100,
            "sub_close_operands": abs(parsed.a.value - parsed.b.value) <= CLOSE_OPERANDS_THRESHOLD,
            "sub_contains_internal_zero": _contains_zero_inside(parsed),
            "sub_leading_digit_changes": borrow_details["borrow_changes_leading_digit"],
        }
    )
    return features


def _multiplication_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["multiplication"])
    if not parsed.parse_succeeded or parsed.operation != "multiplication":
        return features

    features.update(
        {
            "mult_is_tie": parsed.a.value == parsed.b.value,
            "mult_near_10": abs(parsed.a.value - Decimal(10)) <= NEAR_10_DISTANCE
            or abs(parsed.b.value - Decimal(10)) <= NEAR_10_DISTANCE,
            "mult_near_100": abs(parsed.a.value - Decimal(100)) <= NEAR_100_DISTANCE
            or abs(parsed.b.value - Decimal(100)) <= NEAR_100_DISTANCE,
            "mult_can_double_and_halve": _can_double_and_halve(parsed),
        }
    )
    if not _all_integers(parsed.a, parsed.b, parsed.result):
        return features

    digits_a = _integer_digit_count(parsed.a)
    digits_b = _integer_digit_count(parsed.b)
    a = abs(parsed.a.integer_value)
    b = abs(parsed.b.integer_value)
    factors = [a, b]
    features.update(
        {
            "mult_one_digit_by_one_digit": digits_a == 1 and digits_b == 1,
            "mult_one_digit_by_two_digit": sorted((digits_a, digits_b)) == [1, 2],
            "mult_two_digit_by_two_digit": digits_a == 2 and digits_b == 2,
            "mult_has_zero": 0 in factors,
            "mult_has_one": 1 in factors,
            "mult_has_two": 2 in factors,
            "mult_has_five": 5 in factors,
            "mult_has_ten": 10 in factors,
            "mult_has_eleven": 11 in factors,
            "mult_has_nine": 9 in factors,
            "mult_has_twenty_five": 25 in factors,
            "mult_even_factor_present": any(factor % 2 == 0 for factor in factors),
            "mult_both_even": all(factor % 2 == 0 for factor in factors),
            "mult_both_odd": all(factor % 2 == 1 for factor in factors),
            "mult_units_product_ge_10": (a % 10) * (b % 10) >= 10,
            "mult_num_partial_products": digits_a * digits_b,
            "mult_num_partial_products_with_carry": _multiplication_partial_products_with_carry(a, b),
            "mult_result_trailing_zero_count": _trailing_zero_count(abs(parsed.result.integer_value)),
        }
    )
    return features


def _division_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["division"])
    if not parsed.parse_succeeded or parsed.operation != "division":
        return features

    exact = parsed.b.value != 0 and parsed.a.value == parsed.b.value * parsed.result.value
    terminating_decimal = _division_result_terminates(parsed)
    features.update(
        {
            "div_exact": exact,
            "div_by_1": parsed.b.value == 1,
            "div_by_2": parsed.b.value == 2,
            "div_by_5": parsed.b.value == 5,
            "div_by_10": parsed.b.value == 10,
            "div_by_11": parsed.b.value == 11,
            "div_by_25": parsed.b.value == 25,
            "quotient_is_integer": parsed.result.is_integer,
            "quotient_is_small_integer": (
                abs(parsed.result.integer_value) <= SMALL_INTEGER_QUOTIENT_THRESHOLD
                if parsed.result.integer_value is not None
                else None
            ),
            "division_result_terminating_decimal": terminating_decimal,
        }
    )
    return features


def _shortcut_features(parsed: ParsedAttemptRow) -> dict[str, Any]:
    features = _null_feature_group(FEATURE_GROUPS["shortcuts"])
    if not parsed.parse_succeeded:
        return features

    features.update(
        {
            "can_double_and_halve": _can_double_and_halve(parsed),
            "can_use_times_9_as_times_10_minus_1": parsed.operation == "multiplication"
            and (parsed.a.value == 9 or parsed.b.value == 9),
            "can_use_times_5_as_half_times_10": parsed.operation in {"multiplication", "division"}
            and (parsed.a.value == 5 or parsed.b.value == 5),
            "can_use_times_25_as_quarter_times_100": parsed.operation in {"multiplication", "division"}
            and (parsed.a.value == 25 or parsed.b.value == 25),
            "can_use_complement_subtraction": parsed.operation == "subtraction"
            and _can_use_complement_subtraction(parsed),
            "can_use_fact_family": _can_use_fact_family(parsed),
            "can_use_known_square": _can_use_known_square(parsed),
            "can_use_near_square": _can_use_near_square(parsed),
        }
    )
    return features


def _addition_carry_details(a: int, b: int) -> dict[str, Any]:
    details = {
        "requires_carry": False,
        "num_carries": 0,
        "carry_in_units": False,
        "carry_in_tens": False,
        "carry_creates_new_digit": False,
    }
    carry = 0
    digits_a = _digits_lsb(abs(a))
    digits_b = _digits_lsb(abs(b))
    for index in range(max(len(digits_a), len(digits_b))):
        left_digit = digits_a[index] if index < len(digits_a) else 0
        right_digit = digits_b[index] if index < len(digits_b) else 0
        total = left_digit + right_digit + carry
        carry = 1 if total >= 10 else 0
        if carry:
            details["requires_carry"] = True
            details["num_carries"] += 1
            if index == 0:
                details["carry_in_units"] = True
            if index == 1:
                details["carry_in_tens"] = True
    details["carry_creates_new_digit"] = bool(carry)
    return details


def _subtraction_borrow_details(a: int, b: int, result: int) -> dict[str, Any]:
    details = {
        "requires_borrow": False,
        "num_borrows": 0,
        "borrow_in_units": False,
        "borrow_in_tens": False,
        "borrow_across_zero": False,
        "long_borrow_chain_length": 0,
        "borrow_changes_leading_digit": False,
    }
    borrow = 0
    current_chain = 0
    digits_a = _digits_lsb(abs(a))
    digits_b = _digits_lsb(abs(b))
    for index in range(max(len(digits_a), len(digits_b))):
        left_digit = digits_a[index] if index < len(digits_a) else 0
        right_digit = digits_b[index] if index < len(digits_b) else 0
        effective_left = left_digit - borrow
        next_borrow = effective_left < right_digit
        if next_borrow:
            details["requires_borrow"] = True
            details["num_borrows"] += 1
            current_chain += 1
            details["long_borrow_chain_length"] = max(details["long_borrow_chain_length"], current_chain)
            if index == 0:
                details["borrow_in_units"] = True
            if index == 1:
                details["borrow_in_tens"] = True
            if left_digit == 0 or effective_left < 0:
                details["borrow_across_zero"] = True
        else:
            current_chain = 0
        borrow = 1 if next_borrow else 0

    if a != 0:
        original_leading_digit = str(abs(a))[0]
        result_leading_digit = str(abs(result))[0] if result != 0 else "0"
        details["borrow_changes_leading_digit"] = details["requires_borrow"] and (
            original_leading_digit != result_leading_digit
        )
    return details


def _crosses_threshold(parsed: ParsedAttemptRow, threshold: int) -> bool | None:
    if parsed.operation == "addition":
        return parsed.a.integer_value < threshold and parsed.result.integer_value >= threshold
    if parsed.operation == "subtraction":
        return parsed.a.integer_value >= threshold and parsed.result.integer_value < threshold
    if parsed.operation in {"multiplication", "division"}:
        operand_max = max(abs(parsed.a.integer_value), abs(parsed.b.integer_value))
        return operand_max < threshold <= abs(parsed.result.integer_value)
    return None


def _can_double_and_halve(parsed: ParsedAttemptRow) -> bool | None:
    if parsed.operation not in {"multiplication", "division"}:
        return None
    if not parsed.parse_succeeded or not _all_integers(parsed.a, parsed.b):
        return None
    a = abs(parsed.a.integer_value)
    b = abs(parsed.b.integer_value)
    return (a % 2 == 0 or b % 2 == 0) and a > 0 and b > 0


def _can_use_complement_subtraction(parsed: ParsedAttemptRow) -> bool:
    if not _all_integers(parsed.a, parsed.b, parsed.result):
        return False
    a = abs(parsed.a.integer_value)
    b = abs(parsed.b.integer_value)
    result = abs(parsed.result.integer_value)
    return (
        a in {10, 100, 1000}
        or (a % 10 == 0 and b <= 10)
        or (b + result in {10, 100, 1000})
    )


def _can_use_fact_family(parsed: ParsedAttemptRow) -> bool | None:
    if parsed.operation not in {"multiplication", "division"}:
        return None
    if not _all_integers(parsed.a, parsed.b, parsed.result):
        return None
    if parsed.operation == "multiplication":
        return abs(parsed.a.integer_value) <= 12 and abs(parsed.b.integer_value) <= 12
    return abs(parsed.b.integer_value) <= 12 and abs(parsed.result.integer_value) <= 12


def _can_use_known_square(parsed: ParsedAttemptRow) -> bool | None:
    if parsed.operation == "multiplication":
        return parsed.a.value == parsed.b.value if parsed.parse_succeeded else None
    if parsed.operation == "division":
        if not parsed.parse_succeeded or not _all_integers(parsed.a, parsed.b, parsed.result):
            return None
        sqrt_value = int(abs(parsed.a.integer_value) ** 0.5)
        return sqrt_value * sqrt_value == abs(parsed.a.integer_value)
    return None


def _can_use_near_square(parsed: ParsedAttemptRow) -> bool | None:
    if parsed.operation != "multiplication":
        return None
    if not parsed.parse_succeeded or not _all_integers(parsed.a, parsed.b):
        return None
    return abs(parsed.a.integer_value - parsed.b.integer_value) <= 1


def _division_result_terminates(parsed: ParsedAttemptRow) -> bool | None:
    if not parsed.parse_succeeded or parsed.operation != "division" or parsed.b.value == 0:
        return None
    quotient_fraction = Fraction(parsed.a.value) / Fraction(parsed.b.value)
    denominator = quotient_fraction.denominator
    for factor in (2, 5):
        while denominator % factor == 0:
            denominator //= factor
    return denominator == 1


def _multiplication_partial_products_with_carry(a: int, b: int) -> int:
    count = 0
    for left_digit in _digits_lsb(abs(a)):
        for right_digit in _digits_lsb(abs(b)):
            if left_digit * right_digit >= 10:
                count += 1
    return count


def _digits_lsb(value: int) -> list[int]:
    return [int(character) for character in str(abs(value))[::-1]]


def _normalize_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def _numeric_value(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _row_value(row: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return default


def _null_feature_group(feature_names: Iterable[str]) -> dict[str, Any]:
    return {feature_name: None for feature_name in feature_names}


def _integer_digit_count(value: ParsedValue) -> int | None:
    if value.value is None:
        return None
    integer_part = abs(int(value.value.to_integral_value(rounding=ROUND_DOWN)))
    return len(str(integer_part))


def _both_digit_length(parsed: ParsedAttemptRow, digit_length: int) -> bool | None:
    if not _all_integers(parsed.a, parsed.b):
        return None
    return _integer_digit_count(parsed.a) == digit_length and _integer_digit_count(parsed.b) == digit_length


def _all_integers(*values: ParsedValue) -> bool:
    return all(value.is_integer is True for value in values)


def _integer_binary_operation(parsed: ParsedAttemptRow, operation: str) -> bool:
    return parsed.operation == operation and _all_integers(parsed.a, parsed.b, parsed.result)


def _pair_sums_to_target(parsed: ParsedAttemptRow, target: int) -> bool:
    if not parsed.parse_succeeded:
        return False
    pairs = (
        parsed.a.value + parsed.b.value,
        parsed.a.value + parsed.result.value,
        parsed.b.value + parsed.result.value,
    )
    return any(sum_value == target for sum_value in pairs)


def _is_power_of_ten(value: Decimal) -> bool:
    if value <= 0 or value != value.to_integral_value():
        return False
    integer_value = int(value)
    while integer_value > 1 and integer_value % 10 == 0:
        integer_value //= 10
    return integer_value == 1


def _is_offset_from_power_of_ten(value: Decimal, offset: int) -> bool:
    if value <= 0 or value != value.to_integral_value():
        return False
    integer_value = int(value)
    if offset == -1:
        integer_value += 1
    else:
        integer_value -= 1
    return integer_value > 0 and _is_power_of_ten(Decimal(integer_value))


def _shared_place_digit(a: ParsedValue, b: ParsedValue, place: int) -> bool | None:
    if not _all_integers(a, b):
        return None
    if _integer_digit_count(a) <= place or _integer_digit_count(b) <= place:
        return None
    digit_a = (abs(a.integer_value) // (10 ** place)) % 10
    digit_b = (abs(b.integer_value) // (10 ** place)) % 10
    return digit_a == digit_b


def _contains_zero_inside(parsed: ParsedAttemptRow) -> bool | None:
    if not _all_integers(parsed.a, parsed.b, parsed.result):
        return None
    for value in (parsed.a, parsed.b, parsed.result):
        digits = value.integer_digits or ""
        if len(digits) > 2 and "0" in digits[1:-1]:
            return True
    return False


def _digit_sum(value: ParsedValue) -> int | None:
    if value.digit_characters is None:
        return None
    return sum(int(character) for character in value.digit_characters)


def _trailing_zero_count(value: int) -> int | None:
    if value == 0:
        return None
    count = 0
    while value % 10 == 0:
        count += 1
        value //= 10
    return count


def _select_feature_subset(feature_row: Mapping[str, Any], allowed_tiers: set[str]) -> dict[str, Any]:
    return {
        key: value
        for key, value in feature_row.items()
        if FEATURE_TRUST_TIERS.get(key) in allowed_tiers
    }
