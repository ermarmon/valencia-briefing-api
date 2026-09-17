from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import history_store


class BriefingHistoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temporary_directory.name) / "history.json"
        self.path_patch = patch.object(history_store, "HISTORY_FILE_PATH", self.history_path)
        self.limit_patch = patch.object(history_store, "BRIEFING_HISTORY_LIMIT", 3)
        self.path_patch.start()
        self.limit_patch.start()

    def tearDown(self) -> None:
        self.limit_patch.stop()
        self.path_patch.stop()
        self.temporary_directory.cleanup()

    def test_retains_the_three_newest_briefings(self) -> None:
        for text in ("uno", "dos", "tres", "cuatro"):
            history_store.record(text)

        self.assertEqual(
            [entry["text"] for entry in history_store.list_entries(limit=3)],
            ["cuatro", "tres", "dos"],
        )

    def test_repeated_briefing_id_is_idempotent(self) -> None:
        first, created = history_store.record("Buenos días", briefing_id="2026-09-17")
        repeated, repeated_created = history_store.record(
            "Texto distinto que no debe reemplazarlo",
            briefing_id="2026-09-17",
        )

        self.assertTrue(created)
        self.assertFalse(repeated_created)
        self.assertEqual(repeated, first)
        self.assertEqual(len(history_store.list_entries(limit=3)), 1)