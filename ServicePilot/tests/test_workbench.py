"""Offline checks for new presentation and cloud safeguards; no model requests."""
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from servicepilot.deployment import DemoLimiter, DemoBusyError, DemoQuotaError
from servicepilot.web_runtime import web_version, PageConversation
from servicepilot.workbench_ui import successful_results
from test_web_workflow import FakeBackend

PRODUCT = Path(__file__).resolve().parents[1]


class WorkbenchTests(unittest.TestCase):
    def test_no_provider_still_exposes_static_columns(self):
        with patch("servicepilot.deployment.bootstrap_from_environment"), \
             patch("servicepilot.web_runtime.server_ready", return_value=False):
            app = AppTest.from_file(str(PRODUCT / "app.py"), default_timeout=15).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([x.label for x in app.tabs], ["客服体验", "架构总览", "项目介绍", "代码解读"])
        self.assertTrue(app.chat_input[0].disabled)
        self.assertTrue(any("7f9f277" in x.value for x in app.caption))

    def test_examples_fill_only_and_rerender_does_not_query(self):
        backend = FakeBackend()
        conversation = PageConversation(backend)
        app = AppTest.from_file(str(PRODUCT / "app.py"), default_timeout=15)
        app.session_state.conversation = conversation
        app.run()
        next(b for b in app.button if b.label == "查一下 A1001").click().run()
        self.assertEqual(backend.calls, [])
        self.assertEqual(conversation.turns, [])
        self.assertEqual(app.chat_input[0].value, "我的订单 A1001 到哪了？")
        app.run()
        self.assertEqual(backend.calls, [])
        self.assertEqual(len(app.exception), 0)

    def test_failed_turn_cannot_display_success_facts(self):
        turn = {"status": "failed", "events": [{"type": "tool_result", "result": {
            "status": "ok", "order": {"order_id": "A1001"}}}]}
        self.assertEqual(successful_results(turn), [])
        turn["status"] = "completed"
        self.assertEqual(len(successful_results(turn)), 1)
        turn["events"][0]["result"]["status"] = "unavailable"
        self.assertEqual(successful_results(turn), [])

    def test_version_without_git_does_not_claim_commit(self):
        with patch("servicepilot.web_runtime.subprocess.check_output", side_effect=FileNotFoundError):
            version = web_version()
        self.assertIsNone(version["commit"])
        self.assertIsNone(version["worktree_dirty"])
        self.assertTrue(version["source_hashes"])

    def test_demo_limits_are_process_wide_and_release_does_not_reset_budget(self):
        limiter = DemoLimiter(max_concurrent=1, max_requests=2)
        limiter.reserve()
        with self.assertRaises(DemoBusyError):
            limiter.reserve()
        limiter.release()
        limiter.reserve()
        limiter.release()
        with self.assertRaises(DemoQuotaError):
            limiter.reserve()
        self.assertEqual(limiter.active, 0)
        self.assertEqual(limiter.accepted, 2)
