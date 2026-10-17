"""Public source integrity, traversal rejection and read-only reruns; no API."""
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from servicepilot.code_guide import LESSONS
from servicepilot.source_catalog import PUBLIC_FILES, content_hash, excerpt, load_snapshot, source_file
from servicepilot.web_runtime import PageConversation
from test_web_workflow import FakeBackend

PRODUCT = Path(__file__).resolve().parents[1]


class CodeGuideTests(unittest.TestCase):
    def test_cached_old_display_modules_refresh_without_replacing_conversation(self):
        import streamlit as st
        from servicepilot import code_guide, workbench_ui
        st.cache_resource.clear()
        backend = FakeBackend()
        conversation = PageConversation(backend)
        app = AppTest.from_file(str(PRODUCT/'app.py'), default_timeout=20)
        app.session_state.conversation = conversation
        with patch.object(code_guide, "show_code_guide", lambda: st.info("自测问题：旧缓存")), \
             patch.object(workbench_ui, "show_architecture", lambda: st.warning("完整架构图暂不可用。")):
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertFalse(any("自测问题" in e.value for e in app.info))
            self.assertFalse(any("完整架构图暂不可用" in e.value for e in app.warning))
            self.assertTrue(any(b.label == "下载完整 SVG" for b in app.get("download_button")))
            self.assertTrue(any("来源版本" in e.value for e in app.caption))
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.session_state.conversation.session_id, conversation.session_id)
        self.assertEqual(backend.calls, [])
        self.assertEqual(conversation.turns, [])

    def test_architecture_is_original_complete_svg_with_only_date_removed(self):
        original = (PRODUCT/'assets/architecture/servicepilot-system-2026-10-14.svg').read_text(encoding='utf-8')
        public = (PRODUCT/'assets/architecture/servicepilot-system.svg').read_text(encoding='utf-8')
        self.assertIn(" · 2026.10.14", original)
        self.assertEqual(public, original.replace(" · 2026.10.14", ""))

    def test_public_copy_has_no_calendar_dates_or_self_assessment(self):
        backend = FakeBackend()
        app = AppTest.from_file(str(PRODUCT/'app.py'), default_timeout=20)
        app.session_state.conversation = PageConversation(backend)
        app.run()
        self.assertEqual(len(app.exception), 0)
        rendered = "\n".join(e.value for group in (app.caption, app.markdown, app.info, app.code) for e in group)
        for phrase in ("自测问题", "不表示本人", "不代表个人独立", "个人独立实现与掌握"):
            self.assertNotIn(phrase, rendered)
        date_pattern = r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|20\d{2}年\d{1,2}月|10\.(?:11|13|14)"
        self.assertIsNone(re.search(date_pattern, rendered))
        snapshot = load_snapshot()
        self.assertIsNone(re.search(date_pattern, snapshot["release_label"]))
        for item in snapshot["files"].values():
            self.assertIsNone(re.search(date_pattern, item["text"]))
        self.assertIsNone(re.search(date_pattern, (PRODUCT/'assets/architecture/servicepilot-system.svg').read_text(encoding='utf-8')))
        self.assertEqual(backend.calls, [])

    def test_snapshot_complete_matches_real_files_and_all_excerpts(self):
        snapshot = load_snapshot()
        for name in PUBLIC_FILES:
            self.assertEqual(source_file(snapshot, name)["text"], (PRODUCT/name).read_text(encoding="utf-8"))
        for lesson in LESSONS:
            for name, first, last in lesson["parts"]:
                part = excerpt(snapshot, name, first, last)
                self.assertEqual(part["text"], "\n".join(source_file(snapshot, name)["text"].splitlines()[part["start"]-1:part["end"]]))
                self.assertLessEqual(part["end"] - part["start"] + 1, 30)

    def test_not_arbitrary_file_access_and_detects_corruption(self):
        snapshot = load_snapshot()
        for name in ("../.env", ".streamlit/secrets.toml", "C:/Windows/win.ini", "artifacts/web/log.json"):
            with self.assertRaises(ValueError):
                source_file(snapshot, name)
        snapshot["files"]["app.py"]["text"] += "corrupted"
        self.assertNotEqual(content_hash(snapshot["files"]["app.py"]["text"]), snapshot["files"]["app.py"]["sha256"])

    def test_reading_and_file_changes_leave_chat_and_backend_untouched(self):
        backend = FakeBackend()
        conversation = PageConversation(backend)
        app = AppTest.from_file(str(PRODUCT/'app.py'), default_timeout=20)
        app.session_state.conversation = conversation
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.expander[-1].label, "完整代码展示")
        self.assertFalse(app.expander[-1].proto.expanded)
        for name in ("servicepilot/model_config.py", "servicepilot/session.py", "data/orders.json", "app.py"):
            app.selectbox(key="public_source_file").select(name).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.code[-1].value, source_file(load_snapshot(), name)["text"].strip("\n"))
        self.assertEqual(backend.calls, [])
        self.assertEqual(conversation.turns, [])
        self.assertEqual(app.session_state.conversation.session_id, conversation.session_id)
