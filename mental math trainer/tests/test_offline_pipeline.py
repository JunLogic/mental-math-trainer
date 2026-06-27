from __future__ import annotations

import csv
import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.services.baseline_pipeline import _build_weakness_priority_analysis, run_baseline_pipeline
from app.services.dataset_builder import (
    build_attempt_dataset_from_storage,
    build_dataset_rows_from_saved_questions,
    filter_answered,
    filter_by_operation,
    filter_correct_only,
    filter_incorrect_only,
    filter_parse_succeeded,
)
from app.services.storage import SQLiteStorage


class OfflinePipelineTest(unittest.TestCase):
    def test_dataset_builder_constructs_labels_and_filters(self) -> None:
        saved_rows = [
            {
                "id": 1,
                "run_id": 1,
                "mode": "Interview Mode",
                "question_index": 1,
                "base_operation": "addition",
                "result_label": "correct",
                "response_time_ms": 1000,
                "difficulty_at_question": 40.0,
                "used_decimal": False,
                "used_missing_variable": False,
                "answer_role": "result",
                "family_label": "integer addition",
                "difficulty_tag": "carry",
                "left": "9",
                "right": "1",
                "result": "10",
            },
            {
                "id": 2,
                "run_id": 1,
                "mode": "Interview Mode",
                "question_index": 2,
                "base_operation": "division",
                "result_label": "incorrect",
                "response_time_ms": 1500,
                "difficulty_at_question": 42.0,
                "used_decimal": False,
                "used_missing_variable": False,
                "answer_role": "result",
                "family_label": "integer division",
                "difficulty_tag": "larger_division",
                "left": "84",
                "right": "7",
                "result": "12",
            },
            {
                "id": 3,
                "run_id": 1,
                "mode": "Interview Mode",
                "question_index": 3,
                "base_operation": "division",
                "result_label": "unanswered",
                "response_time_ms": 1900,
                "difficulty_at_question": 43.0,
                "used_decimal": True,
                "used_missing_variable": True,
                "answer_role": "right",
                "family_label": "decimal division missing",
                "difficulty_tag": "decimal_pair",
                "left": "8.5",
                "right": "2.5",
                "result": "3.4",
            },
        ]

        dataset_rows = build_dataset_rows_from_saved_questions(saved_rows, use_full_features=False)
        self.assertEqual(dataset_rows[0]["y_error"], 0)
        self.assertEqual(dataset_rows[1]["y_error"], 1)
        self.assertIsNone(dataset_rows[2]["y_error"])
        self.assertAlmostEqual(dataset_rows[0]["y_time_log"], math.log1p(1000), places=6)
        self.assertIsNone(dataset_rows[2]["y_time_log"])
        self.assertEqual(dataset_rows[0]["base_operation"], "addition")
        self.assertTrue(dataset_rows[0]["parse_succeeded"])
        self.assertNotIn("can_use_fact_family", dataset_rows[1])
        self.assertIn("a_value_normalized", dataset_rows[0])

        self.assertEqual(len(filter_parse_succeeded(dataset_rows)), 3)
        self.assertEqual(len(filter_answered(dataset_rows)), 2)
        self.assertEqual(len(filter_correct_only(dataset_rows)), 1)
        self.assertEqual(len(filter_incorrect_only(dataset_rows)), 1)
        self.assertEqual(len(filter_by_operation(dataset_rows, {"division"})), 2)

    def test_pipeline_trains_baselines_and_saves_artefacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "leaderboard.db"
            output_dir = Path(temp_dir) / "artefacts"
            storage = SQLiteStorage(database_path)
            storage.initialize()
            self._seed_database(database_path)

            dataset = build_attempt_dataset_from_storage(storage, use_full_features=False)
            self.assertGreaterEqual(len(dataset.rows), 24)
            self.assertIn("base_operation", dataset.feature_columns)
            self.assertIn("requires_carry", dataset.feature_columns)
            self.assertIn("requires_borrow", dataset.feature_columns)
            self.assertIn("sub_crosses_decade", dataset.feature_columns)
            self.assertIn("a_value_normalized", dataset.rows[0])
            self.assertNotIn("a_value_normalized", dataset.feature_columns)
            self.assertNotIn("b_value_normalized", dataset.feature_columns)
            self.assertNotIn("result_value_normalized", dataset.feature_columns)
            self.assertIn("a_value_normalized", dataset.available_feature_columns)
            self.assertIn("answer_role", dataset.pruned_uninformative_model_columns)
            self.assertIn("used_decimal", dataset.pruned_uninformative_model_columns)
            self.assertIn("used_missing_variable", dataset.pruned_uninformative_model_columns)

            results = run_baseline_pipeline(
                storage=storage,
                output_dir=output_dir,
                use_full_features=False,
                test_size=0.25,
                random_seed=42,
                time_correct_only=False,
            )

            self.assertEqual(results["dataset_summary"]["feature_set"], "core")
            self.assertEqual(results["results"]["error_models"]["status"], "ok")
            self.assertEqual(results["results"]["time_models"]["status"], "ok")
            self.assertTrue((output_dir / "attempt_dataset.csv").exists())
            self.assertTrue((output_dir / "metrics.json").exists())
            self.assertTrue((output_dir / "feature_columns.json").exists())
            self.assertTrue((output_dir / "model_feature_manifests.json").exists())
            self.assertTrue((output_dir / "ablations.json").exists())
            self.assertTrue((output_dir / "error_logistic_regression.pkl").exists())
            self.assertTrue((output_dir / "time_elastic_net.pkl").exists())
            self.assertTrue((output_dir / "residual_rows.csv").exists())
            self.assertTrue((output_dir / "residual_summary.json").exists())
            self.assertTrue((output_dir / "top_log_delta_rows.json").exists())
            self.assertTrue((output_dir / "weakness_priority.json").exists())
            self.assertTrue((output_dir / "weakness_priority.csv").exists())
            self.assertTrue((output_dir / "top_training_targets.json").exists())

            error_metrics = results["results"]["error_models"]["models"]["logistic_regression"]["metrics"]
            time_metrics = results["results"]["time_models"]["models"]["elastic_net"]["metrics"]
            self.assertIn("accuracy", error_metrics)
            self.assertIn("balanced_accuracy", error_metrics)
            self.assertIn("mae", time_metrics)
            self.assertIn("rmse", time_metrics)
            error_split = results["results"]["error_models"]["split"]
            time_split = results["results"]["time_models"]["split"]
            self.assertTrue(set(error_split["train_run_ids"]).isdisjoint(error_split["test_run_ids"]))
            self.assertTrue(set(time_split["train_run_ids"]).isdisjoint(time_split["test_run_ids"]))
            self.assertIn("base_operation", results["model_feature_manifests"]["error_models"]["models"]["logistic_regression"]["model_input_columns"])
            self.assertIn("requires_carry", results["model_feature_manifests"]["time_models"]["models"]["elastic_net"]["model_input_columns"])
            self.assertNotIn("answer_role", results["model_feature_manifests"]["time_models"]["models"]["elastic_net"]["model_input_columns"])
            self.assertNotIn(
                "a_value_normalized",
                results["model_feature_manifests"]["error_models"]["models"]["logistic_regression"]["model_input_columns"],
            )
            self.assertIn(
                "division",
                results["ablations"]["dataset_counts"]["operation_counts"],
            )

            residual_analysis = results["results"]["time_models"]["residual_analysis"]
            self.assertEqual(residual_analysis["status"], "ok")
            self.assertEqual(residual_analysis["analysis_model"], "gradient_boosting_regressor")
            self.assertEqual(residual_analysis["rows"], results["results"]["time_models"]["test_rows"])
            self.assertEqual(residual_analysis["weakness_priority"]["default_view"], "correct_only")
            self.assertIn("all_answered", residual_analysis["weakness_priority"]["available_views"])
            self.assertIn("correct_only", residual_analysis["weakness_priority"]["available_views"])

            with (output_dir / "residual_rows.csv").open("r", encoding="utf-8", newline="") as handle:
                residual_rows = list(csv.DictReader(handle))
            self.assertEqual(len(residual_rows), results["results"]["time_models"]["test_rows"])
            self.assertIn("expected_time_log", residual_rows[0])
            self.assertIn("log_delta", residual_rows[0])
            self.assertIn("residual_band", residual_rows[0])

            with (output_dir / "residual_summary.json").open("r", encoding="utf-8") as handle:
                residual_summary = json.load(handle)
            self.assertEqual(residual_summary["analysis_model"], "gradient_boosting_regressor")
            self.assertEqual(
                residual_summary["definitions"]["log_delta"],
                "actual_time_log - expected_time_log",
            )
            self.assertIn("addition", residual_summary["by_operation"])
            self.assertIn("mildly_slow", residual_summary["band_definitions"])

            with (output_dir / "weakness_priority.json").open("r", encoding="utf-8") as handle:
                weakness_priority = json.load(handle)
            self.assertEqual(weakness_priority["default_view"], "correct_only")
            self.assertEqual(weakness_priority["minimum_support"]["count"], 6)
            self.assertIn("support_count / 12", weakness_priority["priority_scoring"]["rule"])
            self.assertIn("base_operation", weakness_priority["slice_types_considered"]["single_feature_categorical"])
            self.assertIn("subtraction__requires_borrow", {
                item["slice_key"]
                for item in weakness_priority["slice_types_considered"]["structured_combinations"]
            })

    def test_weakness_priority_ranks_supported_slices_and_excludes_tiny_noise(self) -> None:
        residual_rows = []
        for index, log_delta in enumerate((0.6, 0.5, 0.45, 0.4, 0.35, 0.3), start=1):
            residual_rows.append(
                {
                    "saved_question_id": index,
                    "run_id": 1,
                    "question_index": index,
                    "base_operation": "subtraction",
                    "result_label": "correct",
                    "answer_role": "result",
                    "used_decimal": False,
                    "used_missing_variable": False,
                    "requires_borrow": True,
                    "num_borrows": 1,
                    "borrow_across_zero": False,
                    "actual_time_log": 8.0 + log_delta,
                    "expected_time_log": 8.0,
                    "log_delta": log_delta,
                    "residual_band": "breakdown" if log_delta >= 0.5 else "slow",
                }
            )
        for index, log_delta in enumerate((-0.05, 0.0), start=7):
            residual_rows.append(
                {
                    "saved_question_id": index,
                    "run_id": 1,
                    "question_index": index,
                    "base_operation": "subtraction",
                    "result_label": "correct",
                    "answer_role": "result",
                    "used_decimal": False,
                    "used_missing_variable": False,
                    "requires_borrow": False,
                    "num_borrows": 0,
                    "borrow_across_zero": False,
                    "actual_time_log": 8.0 + log_delta,
                    "expected_time_log": 8.0,
                    "log_delta": log_delta,
                    "residual_band": "on_band",
                }
            )
        for index, log_delta in enumerate((0.0, -0.1, 0.05, -0.05), start=9):
            residual_rows.append(
                {
                    "saved_question_id": index,
                    "run_id": 1,
                    "question_index": index,
                    "base_operation": "addition",
                    "result_label": "correct",
                    "answer_role": "result",
                    "used_decimal": False,
                    "used_missing_variable": False,
                    "requires_carry": False,
                    "actual_time_log": 8.0 + log_delta,
                    "expected_time_log": 8.0,
                    "log_delta": log_delta,
                    "residual_band": "on_band",
                }
            )
        for index, log_delta in enumerate((0.9, 0.8, 0.75, 0.7, 0.65), start=13):
            residual_rows.append(
                {
                    "saved_question_id": index,
                    "run_id": 2,
                    "question_index": index,
                    "base_operation": "multiplication",
                    "result_label": "correct",
                    "answer_role": "left",
                    "used_decimal": False,
                    "used_missing_variable": False,
                    "mult_two_digit_by_two_digit": True,
                    "actual_time_log": 8.0 + log_delta,
                    "expected_time_log": 8.0,
                    "log_delta": log_delta,
                    "residual_band": "breakdown",
                }
            )
        for index, log_delta in enumerate((0.2, 0.15), start=18):
            residual_rows.append(
                {
                    "saved_question_id": index,
                    "run_id": 3,
                    "question_index": index,
                    "base_operation": "division",
                    "result_label": "incorrect",
                    "answer_role": "result",
                    "used_decimal": False,
                    "used_missing_variable": True,
                    "actual_time_log": 8.0 + log_delta,
                    "expected_time_log": 8.0,
                    "log_delta": log_delta,
                    "residual_band": "mildly_slow",
                }
            )

        weakness_priority = _build_weakness_priority_analysis(
            residual_rows=residual_rows,
            analysis_model="gradient_boosting_regressor",
            correct_only_source=False,
            split={"strategy": "unit_test"},
        )

        self.assertEqual(weakness_priority["default_view"], "correct_only")
        self.assertIn("correct_only", weakness_priority["available_views"])
        self.assertIn("all_answered", weakness_priority["available_views"])
        ranked_slices = weakness_priority["views"]["correct_only"]["ranked_slices"]
        self.assertGreater(len(ranked_slices), 0)
        top_slice = ranked_slices[0]
        self.assertEqual(top_slice["slice_key"], "subtraction__requires_borrow")
        self.assertEqual(top_slice["support_count"], 6)
        self.assertEqual(top_slice["slow_or_worse_rate"], 1.0)
        self.assertEqual(top_slice["breakdown_rate"], 0.3333)
        expected_score = round(
            (
                max(top_slice["mean_log_delta"], 0.0)
                + 0.5 * max(top_slice["median_log_delta"], 0.0)
            )
            * min(1.0, top_slice["support_count"] / 12)
            * (1.0 + top_slice["slow_or_worse_rate"] + (1.5 * top_slice["breakdown_rate"])),
            6,
        )
        self.assertEqual(top_slice["priority_score"], expected_score)
        self.assertNotIn(
            "multiplication__two_digit_by_two_digit",
            {item["slice_key"] for item in ranked_slices},
        )
        self.assertEqual(
            weakness_priority["top_training_targets"]["targets"][0]["slice_key"],
            "subtraction__requires_borrow",
        )

    def test_pipeline_defaults_time_analysis_to_correct_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "leaderboard.db"
            output_dir = Path(temp_dir) / "artefacts"
            storage = SQLiteStorage(database_path)
            storage.initialize()
            self._seed_database(database_path)

            results = run_baseline_pipeline(
                storage=storage,
                output_dir=output_dir,
                use_full_features=False,
                test_size=0.25,
                random_seed=42,
            )

            self.assertTrue(results["results"]["time_models"]["correct_only"])
            self.assertTrue(results["results"]["time_models"]["residual_analysis"]["correct_only"])
            self.assertEqual(
                results["results"]["time_models"]["residual_analysis"]["weakness_priority"]["default_view"],
                "correct_only",
            )

    def test_dataset_builder_prunes_constant_model_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "leaderboard.db"
            storage = SQLiteStorage(database_path)
            storage.initialize()
            self._seed_database(database_path, run_ids=(1, 3), repeat_sets=2)

            dataset = build_attempt_dataset_from_storage(storage, use_full_features=False)

            self.assertIn("mode", dataset.available_feature_columns)
            self.assertNotIn("mode", dataset.feature_columns)
            self.assertIn("mode", dataset.pruned_uninformative_model_columns)

    def test_pipeline_reports_grouped_split_gracefully_when_too_few_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "leaderboard.db"
            output_dir = Path(temp_dir) / "artefacts"
            storage = SQLiteStorage(database_path)
            storage.initialize()
            self._seed_database(database_path, run_ids=(1,), repeat_sets=2)

            results = run_baseline_pipeline(
                storage=storage,
                output_dir=output_dir,
                use_full_features=False,
                test_size=0.25,
                random_seed=42,
            )

            self.assertEqual(results["results"]["error_models"]["status"], "skipped")
            self.assertIn("at least 2 runs", results["results"]["error_models"]["reason"])
            self.assertEqual(results["results"]["time_models"]["status"], "skipped")

    def _seed_database(
        self,
        database_path: Path,
        run_ids: tuple[int, ...] = (1, 2, 3, 4),
        repeat_sets: int = 1,
    ) -> None:
        run_rows = []
        run_modes = {
            1: "Interview Mode",
            2: "Practice Mode",
            3: "Interview Mode",
            4: "Zetamac Mode",
        }
        for run_id in run_ids:
            run_rows.append(
                (
                    f"2026-03-18T10:{run_id:02d}:00Z",
                    8,
                    8,
                    4,
                    2,
                    0,
                    6,
                    0.6667,
                    1.0 + (run_id * 0.1),
                    "{}",
                    100 + run_id,
                    run_modes.get(run_id, "Interview Mode"),
                    480,
                )
            )
        question_rows = []
        operations = [
            ("addition", "9", "1", "10"),
            ("subtraction", "52", "17", "35"),
            ("multiplication", "25", "16", "400"),
            ("division", "84", "7", "12"),
            ("addition", "95", "5", "100"),
            ("subtraction", "101", "2", "99"),
        ]
        result_labels = ["correct", "incorrect", "correct", "incorrect", "correct", "incorrect"]

        for run_id in run_ids:
            for repeat_index in range(repeat_sets):
                for operation_index, (operation, left, right, result) in enumerate(operations, start=1):
                    question_index = repeat_index * len(operations) + operation_index
                    result_label = result_labels[operation_index - 1]
                    response_time_ms = 700 + (run_id * 100) + (question_index * 75)
                    question_rows.append(
                        (
                            run_id,
                            run_modes.get(run_id, "Interview Mode"),
                            question_index,
                            f"{left} ? {right}",
                            result,
                            result if result_label == "correct" else str(int(float(result)) + 1),
                            1 if result_label == "correct" else 0,
                            result_label,
                            response_time_ms,
                            operation,
                            0,
                            0,
                            left,
                            right,
                            result,
                            "result",
                            f"integer {operation}",
                            "test_case",
                            float(35 + question_index),
                            None,
                            None,
                            operation,
                        )
                    )

        with sqlite3.connect(database_path) as connection:
            connection.executemany(
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
                run_rows,
            )
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


if __name__ == "__main__":
    unittest.main()
