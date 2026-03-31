from __future__ import annotations

import unittest
from statistics import mean

from app.services.config import GenerationSettings, HARD_DIFFICULTY
from app.services.generator import QuestionGenerator


class InterviewModeHardeningTest(unittest.TestCase):
    def test_generation_settings_accept_custom_target_pace_and_initial_difficulty(self) -> None:
        settings = GenerationSettings.from_preset("interview_default", mode="assessment")
        settings.adaptive_enabled = True
        settings.target_pace_seconds = 4.4
        settings.initial_difficulty = 83.5
        settings.validate()

        self.assertEqual(settings.target_pace_seconds, 4.4)
        self.assertEqual(settings.initial_difficulty, 83.5)

        settings.target_pace_seconds = 6.4
        with self.assertRaises(ValueError):
            settings.validate()

    def test_assessment_adaptive_context_biases_toward_harder_operation_mix(self) -> None:
        settings = GenerationSettings.from_preset("interview_default", mode="assessment")
        generator = QuestionGenerator(settings=settings, seed=7)

        baseline = generator._resolve_generation_context(40.0)
        hard = generator._resolve_generation_context(100.0)

        self.assertLess(hard["operation_weights"]["addition"], baseline["operation_weights"]["addition"])
        self.assertLess(hard["operation_weights"]["subtraction"], baseline["operation_weights"]["subtraction"])
        self.assertGreater(hard["operation_weights"]["multiplication"], baseline["operation_weights"]["multiplication"])
        self.assertGreater(hard["operation_weights"]["division"], baseline["operation_weights"]["division"])
        self.assertGreater(hard["decimal_probability"], baseline["decimal_probability"])
        self.assertGreater(hard["missing_variable_probability"], baseline["missing_variable_probability"])

    def test_hard_interview_multiplication_and_division_are_materially_stronger(self) -> None:
        settings = GenerationSettings.from_preset("interview_default", mode="assessment")
        generator = QuestionGenerator(settings=settings, seed=11)

        multiplication_samples = [generator._generate_multiplication(False, HARD_DIFFICULTY) for _ in range(120)]
        division_samples = [generator._generate_division(False, HARD_DIFFICULTY) for _ in range(120)]

        two_digit_share = sum(1 for sample in multiplication_samples if sample.left >= 10 and sample.right >= 10) / len(
            multiplication_samples
        )
        multiplication_tags = [sample.difficulty_tag for sample in multiplication_samples]
        division_tags = [sample.difficulty_tag for sample in division_samples]

        self.assertGreaterEqual(two_digit_share, 0.85)
        self.assertGreaterEqual(multiplication_tags.count("two_digit_pair"), 30)
        self.assertGreaterEqual(multiplication_tags.count("two_digit_multiplication"), 25)
        self.assertGreaterEqual(division_tags.count("integer_pair"), 30)
        self.assertGreaterEqual(mean(float(sample.right) for sample in division_samples), 14.0)
        self.assertGreaterEqual(mean(float(sample.result) for sample in division_samples), 16.0)

    def test_hard_interview_addition_and_subtraction_surface_heavier_patterns(self) -> None:
        settings = GenerationSettings.from_preset("interview_default", mode="assessment")
        generator = QuestionGenerator(settings=settings, seed=19)

        addition_samples = [generator._generate_addition(False, HARD_DIFFICULTY) for _ in range(120)]
        subtraction_samples = [generator._generate_subtraction(False, HARD_DIFFICULTY) for _ in range(120)]

        addition_tags = [sample.difficulty_tag for sample in addition_samples]
        subtraction_tags = [sample.difficulty_tag for sample in subtraction_samples]

        self.assertGreaterEqual(addition_tags.count("multi_carry"), 25)
        self.assertGreaterEqual(subtraction_tags.count("chain_borrow"), 20)
        self.assertGreaterEqual(subtraction_tags.count("across_zero_borrow"), 20)
        self.assertLessEqual(subtraction_tags.count("clean"), 20)


if __name__ == "__main__":
    unittest.main()
