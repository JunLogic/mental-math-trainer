from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.config import DEFAULT_ZETAMAC_OPTIMIZATION_PRESET_NAME, GenerationSettings
from app.services.generator import QuestionGenerator
from app.services.zetamac_optimization import WeaknessArtifactLoader


def _write_top_training_targets(root: Path, targets: list[dict[str, object]]) -> Path:
    artifact_path = root / "phase4_check" / "top_training_targets.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis_model": "gradient_boosting_regressor",
        "default_view": "correct_only",
        "row_filter": "result_label == 'correct'",
        "rows": 144,
        "target_count": len(targets),
        "targets": targets,
    }
    with artifact_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return artifact_path


def _optimization_settings() -> GenerationSettings:
    return GenerationSettings.from_preset(
        DEFAULT_ZETAMAC_OPTIMIZATION_PRESET_NAME,
        mode="zetamac_optimization",
    )


class ZetamacOptimizationModeTest(unittest.TestCase):
    def test_mode_excludes_missing_variable_and_reverse_questions_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = WeaknessArtifactLoader(Path(temp_dir))
            settings = _optimization_settings()
            generator = QuestionGenerator(settings=settings, seed=7, weakness_loader=loader)

            questions = [generator.generate_question() for _ in range(40)]

            self.assertTrue(all(not question.used_missing_variable for question in questions))
            self.assertTrue(all("?" not in question.prompt and "=" not in question.prompt for question in questions))
            self.assertTrue(all(question.used_decimal is False for question in questions))
            self.assertTrue(all(question.metadata["generation_route"] == "rhythm" for question in questions))

    def test_loader_and_generator_fall_back_gracefully_when_artifacts_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = WeaknessArtifactLoader(Path(temp_dir))
            bundle = loader.load_forward_targets()
            self.assertEqual(bundle.status, "artifacts_missing")
            self.assertFalse(bundle.weakness_weighting_applied)

            settings = _optimization_settings()
            generator = QuestionGenerator(settings=settings, seed=11, weakness_loader=loader)
            question = generator.generate_question()
            runtime_policy = generator.runtime_policy_summary()

            self.assertEqual(runtime_policy["status"], "artifacts_missing")
            self.assertFalse(runtime_policy["weakness_weighting_applied"])
            self.assertEqual(question.metadata["generation_route"], "rhythm")
            self.assertFalse(question.used_missing_variable)

    def test_targeted_generation_bias_uses_forward_relevant_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_top_training_targets(
                Path(temp_dir),
                [
                    {
                        "rank": 1,
                        "slice_key": "multiplication__two_digit_by_two_digit",
                        "slice_description": "multiplication + two digit by two digit",
                        "priority_score": 0.82,
                        "support_count": 12,
                        "why_it_matters": "Two-digit multiplication is stalling score runs.",
                        "filter_expression": "base_operation=multiplication & mult_two_digit_by_two_digit=true",
                        "filters": [
                            {"feature": "base_operation", "value": "multiplication"},
                            {"feature": "mult_two_digit_by_two_digit", "value": True},
                        ],
                    }
                ],
            )
            loader = WeaknessArtifactLoader(Path(temp_dir))
            settings = _optimization_settings()
            settings.zetamac_optimization_settings["route_weights"] = {
                "targeted": 1.0,
                "related": 0.0,
                "rhythm": 0.0,
            }
            settings.zetamac_optimization_settings["max_target_streak"] = 50
            generator = QuestionGenerator(settings=settings, seed=19, weakness_loader=loader)

            questions = [generator.generate_question() for _ in range(12)]

            self.assertTrue(all(question.base_operation == "multiplication" for question in questions))
            self.assertTrue(all(question.metadata["generation_route"] == "targeted" for question in questions))
            self.assertTrue(all(question.metadata["generation_target_slice_key"] == "multiplication__two_digit_by_two_digit" for question in questions))
            self.assertTrue(
                all(generator._generated_question_features(question)["mult_two_digit_by_two_digit"] for question in questions)
            )

    def test_reverse_only_artifacts_are_filtered_out_and_do_not_drive_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_top_training_targets(
                Path(temp_dir),
                [
                    {
                        "rank": 1,
                        "slice_key": "division__used_missing_variable",
                        "slice_description": "division + missing variable",
                        "priority_score": 0.91,
                        "support_count": 9,
                        "why_it_matters": "Reverse division is slow.",
                        "filter_expression": "base_operation=division & used_missing_variable=true",
                        "filters": [
                            {"feature": "base_operation", "value": "division"},
                            {"feature": "used_missing_variable", "value": True},
                        ],
                    },
                    {
                        "rank": 2,
                        "slice_key": "answer_role=right",
                        "slice_description": "solve for right operand",
                        "priority_score": 0.77,
                        "support_count": 20,
                        "why_it_matters": "Reverse prompts are slower.",
                        "filter_expression": "answer_role=right",
                        "filters": [
                            {"feature": "answer_role", "value": "right"},
                        ],
                    },
                ],
            )
            loader = WeaknessArtifactLoader(Path(temp_dir))
            bundle = loader.load_forward_targets()

            self.assertEqual(bundle.status, "no_forward_targets")
            self.assertFalse(bundle.weakness_weighting_applied)

            settings = _optimization_settings()
            generator = QuestionGenerator(settings=settings, seed=23, weakness_loader=loader)
            question = generator.generate_question()

            self.assertEqual(generator.runtime_policy_summary()["status"], "no_forward_targets")
            self.assertEqual(question.metadata["generation_route"], "rhythm")
            self.assertFalse(question.used_missing_variable)
            self.assertNotIn("?", question.prompt)

    def test_existing_modes_keep_their_previous_behavior(self) -> None:
        assessment_settings = GenerationSettings.from_preset("interview_default", mode="assessment")
        assessment_settings.decimal_weight = 0
        assessment_settings.missing_variable_weight = 100
        assessment_generator = QuestionGenerator(settings=assessment_settings, seed=29)
        assessment_questions = [assessment_generator.generate_question() for _ in range(30)]

        training_settings = GenerationSettings.from_preset("practice_default", mode="training")
        training_generator = QuestionGenerator(settings=training_settings, seed=31)
        training_question = training_generator.generate_question()

        self.assertTrue(any(question.used_missing_variable for question in assessment_questions))
        self.assertEqual(training_question.metadata.get("generation_route"), None)
        self.assertEqual(len(training_question.options), 4)


if __name__ == "__main__":
    unittest.main()
