from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.services.config import GenerationSettings
from app.services.session_manager import SessionManager
from app.services.storage import SQLiteStorage


class StoragePersistenceTest(unittest.TestCase):
    def test_run_questions_preserve_structured_metadata_and_result_labels(self) -> None:
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

            finished_session = manager.finish_session(session.session_id)

            with sqlite3.connect(database_path) as connection:
                run_id = connection.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchone()[0]

            saved_questions = storage.list_saved_questions(run_id)
            self.assertEqual(len(saved_questions), 3)

            self.assertEqual(saved_questions[0]["result_label"], "correct")
            self.assertEqual(saved_questions[1]["result_label"], "incorrect")
            self.assertEqual(saved_questions[2]["result_label"], "unanswered")

            self.assertEqual(saved_questions[0]["selected_option_index"], first_question.correct_option_index)
            self.assertEqual(saved_questions[0]["correct_option_index"], first_question.correct_option_index)
            self.assertEqual(saved_questions[1]["selected_option_index"], incorrect_index)
            self.assertEqual(saved_questions[1]["correct_option_index"], second_question.correct_option_index)

            for saved_question in saved_questions:
                self.assertIn(saved_question["base_operation"], {"addition", "subtraction", "multiplication", "division"})
                self.assertIsInstance(saved_question["used_decimal"], bool)
                self.assertIsInstance(saved_question["used_missing_variable"], bool)
                self.assertIsNotNone(saved_question["left"])
                self.assertIsNotNone(saved_question["right"])
                self.assertIsNotNone(saved_question["result"])
                self.assertIsNotNone(saved_question["answer_role"])
                self.assertIsNotNone(saved_question["family_label"])
                self.assertIsNotNone(saved_question["difficulty_tag"])

            self.assertEqual(finished_session.unanswered, 1)
            self.assertEqual(len(storage.leaderboard()), 1)


if __name__ == "__main__":
    unittest.main()
