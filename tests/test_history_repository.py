"""Migrations, local retention/privacy, audit integrity, and restart safety."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from localmind.application.use_cases.conversation_history import (
    WELCOME,
    ConversationHistory,
)
from localmind.domain.history import HistoryError
from localmind.domain.organization import FileIdentity, PhotoMove, PhotoPlan
from localmind.infrastructure.persistence.history import (
    SQLiteConversationRepository,
    redact,
)


class HistoryRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "history.sqlite3"
        self.now = 1800000000.0
        self.repo = SQLiteConversationRepository(self.path, lambda: self.now)
        self.snapshot = self.repo.initialize(WELCOME)
        self.id = self.snapshot.conversation_id

    def query(self, sql, params=()):
        with sqlite3.connect(self.path) as db:
            return db.execute(sql, params).fetchall()

    def plan(self):
        return PhotoPlan(
            "plan-1", "/chosen/photos", "type",
            (PhotoMove("password=abc.jpg", "Organized Photos/JPEG/a.jpg", FileIdentity(1, 2, 3, 4)),),
            0, 0, 1,
        )

    def test_initial_migration_is_versioned_indexed_and_foreign_key_safe(self):
        self.assertEqual(self.query("PRAGMA user_version"), [(1,)])
        self.assertEqual(self.query("PRAGMA journal_mode"), [("wal",)])
        self.assertEqual(len(self.query("SELECT name FROM sqlite_master WHERE type='index' AND name='messages_conversation_time'")), 1)
        with self.assertRaises(HistoryError):
            self.repo.append_message("does-not-exist", "user", "orphan")
        self.assertEqual(self.repo.open_conversation(self.id).messages, self.snapshot.messages)

    def test_restart_restores_messages_in_order_and_structured_context(self):
        for text in ["first request", "second request", "third request"]:
            self.repo.append_message(self.id, "user", text)
        self.repo.save_context(self.id, {"workspace": "/chosen/photos", "last_tool": "organize_photos"})
        restarted = SQLiteConversationRepository(self.path, lambda: self.now).initialize(WELCOME)
        self.assertEqual(restarted.conversation_id, self.id)
        self.assertEqual([m.text for m in restarted.messages[1:]], ["first request", "second request", "third request"])
        self.assertEqual(restarted.context["workspace"], "/chosen/photos")

    def test_restart_reopens_the_selected_older_conversation(self):
        self.repo.new_conversation(WELCOME)
        self.repo.open_conversation(self.id)
        restarted = SQLiteConversationRepository(self.path, lambda: self.now).initialize(WELCOME)
        self.assertEqual(restarted.conversation_id, self.id)

    def test_unknown_context_fields_and_unbounded_values_are_rejected(self):
        for value in [{"raw_prompt": "secret"}, {"workspace": "x" * 5000}, {"last_tool": 12}]:
            with self.subTest(value=value), self.assertRaises(HistoryError):
                self.repo.save_context(self.id, value)

    def test_plan_approval_and_execution_are_linked_and_json_remains_valid_after_redaction(self):
        self.repo.save_plan(self.id, self.plan())
        self.repo.record_approval(self.id, "plan-1", True, "button")
        self.repo.record_event(self.id, "plan-1", "apply", "completed", "1 image moved")
        payload, state = self.query("SELECT payload,state FROM action_plans")[0]
        self.assertEqual(state, "completed")
        self.assertEqual(json.loads(payload)["moves"][0]["source"], "password=[REDACTED]")
        self.assertEqual(self.query("SELECT approved,source FROM approvals"), [(1, "button")])
        self.assertEqual(self.query("SELECT plan_id FROM execution_events"), [("plan-1",)])

    def test_prior_approval_never_survives_restart_as_executable_state(self):
        self.repo.save_plan(self.id, self.plan())
        self.repo.record_approval(self.id, "plan-1", True, "chat")
        self.repo.initialize(WELCOME)
        self.assertEqual(self.query("SELECT state FROM action_plans"), [("expired",)])
        self.assertEqual(self.query("SELECT approved FROM approvals"), [(1,)])

    def test_cross_conversation_approval_is_rejected(self):
        self.repo.save_plan(self.id, self.plan())
        other = self.repo.new_conversation(WELCOME).conversation_id
        with self.assertRaises(HistoryError):
            self.repo.record_approval(other, "plan-1", True, "button")
        self.assertEqual(self.query("SELECT COUNT(*) FROM approvals"), [(0,)])

    def test_credential_patterns_are_redacted_before_storage(self):
        sensitive = "api_key=supersecret password: 'two words' Bearer abcdefghijklmnop sk-" + "Z" * 25
        self.repo.append_message(self.id, "user", sensitive)
        text = self.repo.open_conversation(self.id).messages[-1].text
        for secret in ["supersecret", "two words", "abcdefghijklmnop", "Z" * 25]:
            self.assertNotIn(secret, text)
        self.assertIn("REDACTED", text)
        self.assertNotIn("private-value", redact("-----BEGIN PRIVATE KEY-----\nprivate-value\n-----END PRIVATE KEY-----"))

    def test_sql_like_messages_are_data_not_commands(self):
        text = "'; DROP TABLE messages; --"
        self.repo.append_message(self.id, "user", text)
        self.assertEqual(self.repo.open_conversation(self.id).messages[-1].text, text)

    def test_retention_prunes_old_data_and_rejects_unsupported_values(self):
        self.repo.append_message(self.id, "user", "old")
        self.now += 8 * 86400
        latest = self.repo.new_conversation(WELCOME)
        result = self.repo.set_retention(latest.conversation_id, 7)
        self.assertEqual(result.retention_days, 7)
        self.assertEqual(len(result.conversations), 1)
        with self.assertRaises(HistoryError):
            self.repo.open_conversation(self.id)
        with self.assertRaises(HistoryError):
            ConversationHistory(self.repo).change_retention(latest.conversation_id, -1)

    def test_clear_cascades_audit_but_preserves_independent_undo_and_settings(self):
        undo = self.path.parent / "photo-operations.sqlite3"
        undo.write_bytes(b"independent undo data")
        self.repo.save_plan(self.id, self.plan())
        self.repo.record_approval(self.id, "plan-1", False, "discard")
        self.repo.record_event(self.id, "plan-1", "preview", "denied", "declined")
        self.repo.save_context(self.id, {"workspace": "/chosen/photos"})
        fresh = self.repo.clear(WELCOME)
        self.assertNotEqual(fresh.conversation_id, self.id)
        for table in ["action_plans", "approvals", "execution_events", "contexts"]:
            self.assertEqual(self.query(f"SELECT COUNT(*) FROM {table}"), [(0,)])
        self.assertEqual(undo.read_bytes(), b"independent undo data")
        self.assertEqual(fresh.retention_days, 30)

    def test_newer_schema_and_unversioned_or_corrupt_database_are_not_reset(self):
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaisesRegex(HistoryError, "newer"):
            self.repo.initialize(WELCOME)
        self.assertEqual(self.query("PRAGMA user_version"), [(99,)])
        unknown_path = self.path.parent / "unknown.sqlite3"
        with sqlite3.connect(unknown_path) as db:
            db.execute("CREATE TABLE important(value TEXT)")
            db.execute("INSERT INTO important VALUES ('keep')")
        with self.assertRaisesRegex(HistoryError, "unknown schema"):
            SQLiteConversationRepository(unknown_path).initialize(WELCOME)
        with sqlite3.connect(unknown_path) as db:
            self.assertEqual(db.execute("SELECT * FROM important").fetchall(), [("keep",)])
        corrupt = self.path.parent / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a database")
        with self.assertRaises(HistoryError):
            SQLiteConversationRepository(corrupt).initialize(WELCOME)
        self.assertEqual(corrupt.read_bytes(), b"not a database")

    def test_bounded_reads_and_storage_keep_recent_messages(self):
        for i in range(1050):
            self.repo.append_message(self.id, "assistant", f"message {i}")
        result = self.repo.open_conversation(self.id)
        self.assertEqual(len(result.messages), 100)
        self.assertEqual(result.messages[0].text, "message 950")
        self.assertEqual(result.messages[-1].text, "message 1049")
        self.assertEqual(self.query("SELECT COUNT(*) FROM messages"), [(1000,)])


if __name__ == "__main__":
    unittest.main()
