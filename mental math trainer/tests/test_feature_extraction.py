from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.services.config import GenerationSettings
from app.services.feature_extraction import (
    FEATURE_VERSION,
    core_feature_names,
    extract_core_saved_question_feature_rows,
    extract_core_saved_question_features,
    extract_saved_question_feature_rows,
    extract_saved_question_features,
    feature_names_for_tier,
    feature_manifest,
)
from app.services.session_manager import SessionManager
from app.services.storage import SQLiteStorage


class FeatureExtractionTest(unittest.TestCase):
    def _base_row(
        self,
        *,
        operation: str,
        left: str,
        right: str,
        result: str,
        used_decimal: bool = False,
        used_missing_variable: bool = False,
        answer_role: str = "result",
        result_label: str = "correct",
        response_time_ms: int = 1000,
    ) -> dict[str, object]:
        return {
            "id": 1,
            "run_id": 10,
            "mode": "Interview Mode",
            "question_index": 1,
            "base_operation": operation,
            "used_decimal": used_decimal,
            "used_missing_variable": used_missing_variable,
            "answer_role": answer_role,
            "family_label": f"{'decimal' if used_decimal else 'integer'} {operation}",
            "difficulty_tag": "test_case",
            "difficulty_at_question": 40.0,
            "result_label": result_label,
            "response_time_ms": response_time_ms,
            "left": left,
            "right": right,
            "result": result,
        }

    def test_addition_carry_cases_cover_no_carry_single_carry_and_multiple_carries(self) -> None:
        cases = [
            ("12", "23", "35", False, 0, False, False, False),
            ("19", "4", "23", True, 1, True, False, False),
            ("58", "47", "105", True, 2, True, True, True),
            ("90", "10", "100", True, 1, False, True, True),
            ("95", "5", "100", True, 2, True, True, True),
        ]

        for left, right, result, requires_carry, num_carries, carry_units, carry_tens, creates_new_digit in cases:
            with self.subTest(left=left, right=right, result=result):
                features = extract_saved_question_features(
                    self._base_row(operation="addition", left=left, right=right, result=result)
                )
                self.assertEqual(features["feature_version"], FEATURE_VERSION)
                self.assertTrue(features["parse_succeeded"])
                self.assertEqual(features["requires_carry"], requires_carry)
                self.assertEqual(features["num_carries"], num_carries)
                self.assertEqual(features["carry_in_units"], carry_units)
                self.assertEqual(features["carry_in_tens"], carry_tens)
                self.assertEqual(features["carry_creates_new_digit"], creates_new_digit)

    def test_subtraction_borrow_cases_cover_zero_edges_and_chains(self) -> None:
        cases = [
            ("54", "12", "42", False, 0, False, False, False, 0, False),
            ("52", "17", "35", True, 1, True, False, False, 1, True),
            ("101", "2", "99", True, 2, True, True, True, 2, True),
            ("100", "99", "1", True, 2, True, True, True, 2, False),
            ("1000", "1", "999", True, 3, True, True, True, 3, True),
            ("1002", "587", "415", True, 3, True, True, True, 3, True),
        ]

        for (
            left,
            right,
            result,
            requires_borrow,
            num_borrows,
            borrow_units,
            borrow_tens,
            across_zero,
            chain_length,
            leading_change,
        ) in cases:
            with self.subTest(left=left, right=right, result=result):
                features = extract_saved_question_features(
                    self._base_row(operation="subtraction", left=left, right=right, result=result)
                )
                self.assertEqual(features["requires_borrow"], requires_borrow)
                self.assertEqual(features["num_borrows"], num_borrows)
                self.assertEqual(features["borrow_in_units"], borrow_units)
                self.assertEqual(features["borrow_in_tens"], borrow_tens)
                self.assertEqual(features["borrow_across_zero"], across_zero)
                self.assertEqual(features["long_borrow_chain_length"], chain_length)
                self.assertEqual(features["borrow_changes_leading_digit"], leading_change)

    def test_threshold_and_boundary_cases_are_explicit(self) -> None:
        addition_cross_10 = extract_saved_question_features(
            self._base_row(operation="addition", left="9", right="1", result="10")
        )
        addition_cross_100 = extract_saved_question_features(
            self._base_row(operation="addition", left="95", right="5", result="100")
        )
        subtraction_cross_10 = extract_saved_question_features(
            self._base_row(operation="subtraction", left="12", right="3", result="9")
        )
        subtraction_cross_century = extract_saved_question_features(
            self._base_row(operation="subtraction", left="1002", right="587", result="415")
        )

        self.assertTrue(addition_cross_10["crosses_10"])
        self.assertFalse(addition_cross_10["crosses_100"])
        self.assertTrue(addition_cross_10["addition_crosses_decade"])
        self.assertFalse(addition_cross_10["addition_crosses_century"])

        self.assertTrue(addition_cross_100["crosses_100"])
        self.assertTrue(addition_cross_100["addition_crosses_decade"])
        self.assertTrue(addition_cross_100["addition_crosses_century"])

        self.assertTrue(subtraction_cross_10["crosses_10"])
        self.assertTrue(subtraction_cross_10["sub_crosses_decade"])
        self.assertFalse(subtraction_cross_10["sub_crosses_century"])

        self.assertTrue(subtraction_cross_century["crosses_1000"])
        self.assertTrue(subtraction_cross_century["sub_crosses_century"])

    def test_multiplication_features_capture_shortcuts_and_sensitive_fields(self) -> None:
        features = extract_saved_question_features(
            self._base_row(operation="multiplication", left="25", right="16", result="400")
        )

        self.assertTrue(features["mult_two_digit_by_two_digit"])
        self.assertTrue(features["mult_has_twenty_five"])
        self.assertTrue(features["mult_even_factor_present"])
        self.assertEqual(features["mult_num_partial_products"], 4)
        self.assertEqual(features["mult_num_partial_products_with_carry"], 2)
        self.assertEqual(features["mult_result_trailing_zero_count"], 2)
        self.assertTrue(features["mult_can_double_and_halve"])
        self.assertTrue(features["can_use_times_25_as_quarter_times_100"])

    def test_decimal_rows_disable_integer_only_features_cleanly(self) -> None:
        decimal_features = extract_saved_question_features(
            self._base_row(
                operation="addition",
                left="7.2",
                right="5.8",
                result="13.0",
                used_decimal=True,
            )
        )

        self.assertTrue(decimal_features["parse_succeeded"])
        self.assertIsNone(decimal_features["requires_carry"])
        self.assertIsNone(decimal_features["requires_borrow"])
        self.assertIsNone(decimal_features["a_even"])
        self.assertIsNone(decimal_features["shared_units_digit"])
        self.assertIsNone(decimal_features["addition_units_sum"])
        self.assertEqual(decimal_features["distance_a_to_10"], 2.8)
        self.assertTrue(decimal_features["addition_near_doubles"] is False)

    def test_division_and_decimal_missing_variable_features_are_gated_cleanly(self) -> None:
        integer_division = extract_saved_question_features(
            self._base_row(operation="division", left="84", right="7", result="12")
        )
        decimal_missing = extract_saved_question_features(
            self._base_row(
                operation="division",
                left="8.5",
                right="2.5",
                result="3.4",
                used_decimal=True,
                used_missing_variable=True,
                answer_role="right",
                result_label="unanswered",
                response_time_ms=900,
            )
        )

        self.assertTrue(integer_division["div_exact"])
        self.assertTrue(integer_division["quotient_is_integer"])
        self.assertTrue(integer_division["quotient_is_small_integer"])
        self.assertTrue(integer_division["division_result_terminating_decimal"])
        self.assertTrue(integer_division["can_use_fact_family"])

        self.assertTrue(decimal_missing["parse_succeeded"])
        self.assertEqual(decimal_missing["answer_role"], "right")
        self.assertEqual(decimal_missing["b_value_normalized"], "2.5")
        self.assertIsNone(decimal_missing["a_even"])
        self.assertIsNone(decimal_missing["requires_borrow"])
        self.assertFalse(decimal_missing["quotient_is_integer"])
        self.assertTrue(decimal_missing["division_result_terminating_decimal"])

    def test_missing_variable_rows_preserve_answer_role_while_structural_core_stays_consistent(self) -> None:
        left_missing = extract_saved_question_features(
            self._base_row(
                operation="addition",
                left="8",
                right="7",
                result="15",
                used_missing_variable=True,
                answer_role="left",
            )
        )
        right_missing = extract_saved_question_features(
            self._base_row(
                operation="addition",
                left="8",
                right="7",
                result="15",
                used_missing_variable=True,
                answer_role="right",
            )
        )

        self.assertEqual(left_missing["answer_role"], "left")
        self.assertEqual(right_missing["answer_role"], "right")
        for key in ("max_operand", "sum_operands", "requires_carry", "addition_crosses_decade"):
            self.assertEqual(left_missing[key], right_missing[key])

    def test_manifest_tiers_and_core_only_exports_are_versioned_and_filtered(self) -> None:
        manifest = feature_manifest()
        rows = [
            self._base_row(operation="addition", left="9", right="1", result="10"),
            self._base_row(operation="division", left="96", right="8", result="12"),
        ]

        full_features = extract_saved_question_feature_rows(rows)
        core_features = extract_core_saved_question_feature_rows(rows)
        single_core = extract_core_saved_question_features(rows[0])

        self.assertEqual(manifest["version"], FEATURE_VERSION)
        self.assertEqual(manifest["default_model_export"], "core_structural")
        self.assertIn("core_structural", manifest["trust_tiers"])
        self.assertIn("derived_sensitive", manifest["trust_tiers"])
        self.assertIn("heuristic_shortcut", manifest["trust_tiers"])
        self.assertIn("can_use_fact_family", feature_names_for_tier("heuristic_shortcut"))
        self.assertIn("requires_carry", core_feature_names())
        self.assertIn("sub_crosses_decade", core_feature_names())
        self.assertIn("addition_near_doubles", feature_names_for_tier("derived_sensitive"))
        self.assertIn("max_operand", core_feature_names())

        self.assertEqual(len(full_features), 2)
        self.assertEqual(len(core_features), 2)
        self.assertTrue(all(feature["feature_version"] == FEATURE_VERSION for feature in full_features))
        self.assertTrue(all(feature["feature_version"] == FEATURE_VERSION for feature in core_features))
        self.assertIn("max_operand", single_core)
        self.assertIn("requires_carry", single_core)
        self.assertIn("addition_crosses_decade", single_core)
        self.assertNotIn("can_use_fact_family", single_core)
        self.assertNotIn("mult_num_partial_products_with_carry", single_core)

    def test_storage_helpers_build_full_and_core_offline_features_from_persisted_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "leaderboard.db"
            storage = SQLiteStorage(database_path)
            storage.initialize()
            manager = SessionManager(storage)

            settings = GenerationSettings.from_preset("practice_default")
            session = manager.start_session(settings)

            first_question = session.questions[0]
            manager.answer_question(
                session.session_id,
                selected_option_index=first_question.correct_option_index,
                question_number=1,
            )

            session = manager.get_session(session.session_id)
            second_question = session.questions[1]
            incorrect_index = 0 if second_question.correct_option_index != 0 else 1
            manager.answer_question(
                session.session_id,
                selected_option_index=incorrect_index,
                question_number=2,
            )

            manager.finish_session(session.session_id)

            with sqlite3.connect(database_path) as connection:
                run_id = connection.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchone()[0]

            full_feature_rows = storage.build_saved_question_features(run_id)
            core_feature_rows = storage.build_saved_question_core_features(run_id)

            self.assertEqual(len(full_feature_rows), 3)
            self.assertEqual(len(core_feature_rows), 3)
            self.assertEqual(full_feature_rows[0]["feature_version"], FEATURE_VERSION)
            self.assertEqual(full_feature_rows[0]["result_label"], "correct")
            self.assertEqual(full_feature_rows[1]["result_label"], "incorrect")
            self.assertEqual(full_feature_rows[2]["result_label"], "unanswered")
            self.assertTrue(all(row["parse_succeeded"] for row in full_feature_rows))
            self.assertTrue(all("max_operand" in row for row in core_feature_rows))
            self.assertTrue(all("requires_carry" in row for row in core_feature_rows))
            self.assertTrue(all("can_use_fact_family" not in row for row in core_feature_rows))


if __name__ == "__main__":
    unittest.main()
