from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.api.routes import resolve_settings
from app.api.schemas import GameStartRequest
from app.services.config import GenerationSettings
from app.services.session_manager import SessionManager
from app.services.storage import SQLiteStorage


class GameplaySettingsTest(unittest.TestCase):
    def test_resolve_settings_disables_incompatible_wrong_penalty_when_auto_advance_is_on(self) -> None:
        settings = resolve_settings(
            GameStartRequest(
                mode="assessment",
                preset_name="interview_default",
                auto_advance_on_correct=True,
                wrong_answer_penalty=True,
            )
        )

        self.assertTrue(settings.auto_advance_on_correct)
        self.assertFalse(settings.wrong_answer_penalty)

    def test_resolve_settings_keeps_wrong_penalty_available_for_training_mode(self) -> None:
        settings = resolve_settings(
            GameStartRequest(
                mode="training",
                preset_name="practice_default",
                auto_advance_on_correct=True,
                wrong_answer_penalty=True,
            )
        )

        self.assertFalse(settings.auto_advance_on_correct)
        self.assertTrue(settings.wrong_answer_penalty)

    def test_session_payload_includes_auto_advance_match_answer_only_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "leaderboard.db"
            storage = SQLiteStorage(database_path)
            storage.initialize()
            manager = SessionManager(storage)

            settings = GenerationSettings.from_preset("interview_default")
            settings.auto_advance_on_correct = True
            session = manager.start_session(settings)
            payload = manager.build_session_payload(session)

            self.assertEqual(
                payload["question"]["auto_advance_match_answer"],
                session.questions[0].correct_answer,
            )

            settings = GenerationSettings.from_preset("interview_default")
            settings.auto_advance_on_correct = False
            second_session = manager.start_session(settings)
            second_payload = manager.build_session_payload(second_session)

            self.assertNotIn("auto_advance_match_answer", second_payload["question"])

    def test_session_payload_reports_latest_answer_result_for_penalty_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "leaderboard.db"
            storage = SQLiteStorage(database_path)
            storage.initialize()
            manager = SessionManager(storage)

            settings = GenerationSettings.from_preset("practice_default")
            session = manager.start_session(settings)

            first_question = session.questions[0]
            incorrect_index = 0 if first_question.correct_option_index != 0 else 1
            session = manager.answer_question(
                session.session_id,
                selected_option_index=incorrect_index,
                question_number=1,
            )
            payload = manager.build_session_payload(session)

            self.assertEqual(payload["latest_answer"]["question_number"], 1)
            self.assertEqual(payload["latest_answer"]["result"], "incorrect")
            self.assertEqual(
                payload["latest_answer"]["correct_answer"],
                first_question.correct_answer,
            )


if __name__ == "__main__":
    unittest.main()
