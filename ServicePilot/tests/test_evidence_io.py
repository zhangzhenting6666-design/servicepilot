"""Local file-lock checks; no API calls and no production evidence overwritten."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from servicepilot.evidence_io import atomic_write_text
from scripts.run_order_customer_service import save


class EvidenceWriteTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Requires actual Windows sharing semantics")
    def test_real_reader_lock_release_retries_disk_only_and_keeps_redaction(self):
        with tempfile.TemporaryDirectory(prefix="servicepilot-write-test-") as directory:
            path = Path(directory) / "record.json"
            path.write_text("{}", encoding="utf-8")
            ready = threading.Event()
            def reader():
                with path.open("rb"):
                    ready.set()
                    time.sleep(0.15)
            thread = threading.Thread(target=reader)
            thread.start()
            self.assertTrue(ready.wait(2))
            try:
                save(path, {"sessions": [], "message": "sk-unit-only"}, "sk-unit-only")
            finally:
                thread.join(timeout=2)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["message"], "[密钥已隐藏]")
            self.assertFalse(saved["api_request_attempted"])
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_persistent_lock_is_bounded_and_old_record_survives(self):
        with tempfile.TemporaryDirectory(prefix="servicepilot-write-test-") as directory:
            path = Path(directory) / "record.json"
            path.write_text("old", encoding="utf-8")
            error = PermissionError("offline lock")
            error.winerror = 5
            with patch.object(Path, "replace", side_effect=error) as replace, \
                 patch("servicepilot.evidence_io.time.sleep") as sleep:
                with self.assertRaises(PermissionError):
                    atomic_write_text(path, "new")
                self.assertEqual(replace.call_count, 8)
                self.assertEqual(sleep.call_count, 7)
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])
