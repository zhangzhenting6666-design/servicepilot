"""Offline UI/controller tests. Test replies are never live acceptance evidence."""
import asyncio
from concurrent.futures import Future
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from servicepilot.web_runtime import PageConversation, SessionBackend

PRODUCT = Path(__file__).resolve().parents[1]


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.futures = []
        self.resets = []
        self.fail_reset = False

    def ask(self, question):
        self.calls.append(question)
        future = Future()
        self.futures.append(future)
        return future

    def reset(self, fault=False):
        if self.fail_reset:
            raise RuntimeError("test reset failure")
        self.resets.append(fault)


def complete(backend, **overrides):
    result = {"status": "completed", "final_answer": "离线测试答复", "events": []}
    result.update(overrides)
    backend.futures[-1].set_result(result)


class ControllerTests(unittest.TestCase):
    def test_duplicate_busy_empty_old_owner_and_reset(self):
        b = FakeBackend()
        c = PageConversation(b)
        owner = c.session_id
        self.assertEqual(c.submit("  ", "empty", owner), "请输入问题")
        self.assertIsNone(c.submit("帮我查一下订单", "r1", owner))
        self.assertIsNotNone(c.submit("再发一次", "r2", owner))
        self.assertIsNotNone(c.reset())
        self.assertEqual(b.resets, [])
        complete(b)
        self.assertTrue(c.collect())
        self.assertFalse(c.collect())
        self.assertIsNotNone(c.submit("不同问题", "r1", owner))
        self.assertIsNotNone(c.submit("帮我查一下订单", "r3", owner))
        self.assertIsNone(c.reset())
        self.assertNotEqual(owner, c.session_id)
        self.assertEqual(c.turns, [])
        self.assertIsNotNone(c.submit("A1002", "old", owner))
        self.assertEqual(b.calls, ["帮我查一下订单"])

    def test_isolation_reset_failure_and_stale_response_guard(self):
        b1, b2 = FakeBackend(), FakeBackend()
        c1, c2 = PageConversation(b1), PageConversation(b2)
        c1.submit("A1001", "r1", c1.session_id)
        self.assertEqual(c2.turns, [])
        complete(b1)
        c1.collect()
        old = c1.session_id
        b1.fail_reset = True
        self.assertIsNotNone(c1.reset())
        self.assertEqual(old, c1.session_id)
        self.assertEqual(len(c1.turns), 1)
        c2.submit("A1002", "r2", c2.session_id)
        # Defensive ownership check even if state were replaced outside supported reset.
        c2.session_id = "replacement"
        c2.turns = []
        complete(b2)
        c2.collect()
        self.assertEqual(c2.turns, [])
        self.assertEqual(c2.report["controls"][-1]["action"], "stale_response_ignored")

    def test_empty_and_failed_response_redaction_and_business_status(self):
        b = FakeBackend()
        with tempfile.TemporaryDirectory() as d:
            c = PageConversation(b, key="sk-unit-private", evidence_dir=Path(d))
            c.submit("sk-unit-private", "r1", c.session_id)
            complete(b, final_answer="")
            c.collect()
            self.assertEqual(c.turns[-1]["error_type"], "EmptyResponse")
            c.submit("故障", "r2", c.session_id)
            b.futures[-1].set_exception(RuntimeError("Bearer private-value"))
            c.collect()
            self.assertEqual(c.turns[-1]["status"], "failed")
            c.submit("查无记录", "r3", c.session_id)
            complete(b, events=[{"type": "tool_result", "tool": "query_order", "result": {"status": "not_found"}}])
            c.collect()
            self.assertEqual(c.turns[-1]["status"], "completed")
            text = next(Path(d).glob("*.json")).read_text(encoding="utf-8")
            self.assertNotIn("sk-unit-private", text)
            self.assertNotIn("private-value", text)
            self.assertEqual(json.loads(text)["evidence_kind"], "offline_test")

    def test_backend_keeps_one_async_loop_and_recreates_order_context(self):
        class Client:
            async def close(self):
                pass
        class Session:
            def __init__(self, config, source=None):
                self.questions = []
                self.source = source
            async def ask(self, question):
                self.questions.append(question)
                return {"loop": id(asyncio.get_running_loop()), "history": list(self.questions)}
        with patch("servicepilot.web_runtime.create_client_config", return_value=(Client(), object())), \
             patch("servicepilot.web_runtime.OrderSession", Session):
            backend = SessionBackend("unit-only")
            try:
                one = backend.ask("中文问题").result()
                two = backend.ask("补充编号").result()
                self.assertEqual(one["loop"], two["loop"])
                self.assertEqual(two["history"], ["中文问题", "补充编号"])
                old = backend.session
                backend.reset(True)
                self.assertIsNot(old, backend.session)
                three = backend.ask("新问题").result()
                self.assertEqual(three["history"], ["新问题"])
                self.assertIsNotNone(backend.session.source)
            finally:
                backend.close()


class OfflinePageTests(unittest.TestCase):
    def make_page(self):
        b = FakeBackend()
        c = PageConversation(b)
        at = AppTest.from_file(str(PRODUCT / "app.py"), default_timeout=15)
        at.session_state.conversation = c
        at.run()
        self.assertEqual(len(at.exception), 0)
        return at, b, c

    def test_chinese_input_loading_duplicate_and_reset_confirmation(self):
        at, b, c = self.make_page()
        at.chat_input[0].set_value("帮我查一下订单").run()
        self.assertEqual(b.calls, ["帮我查一下订单"])
        self.assertTrue(at.chat_input[0].disabled)
        self.assertTrue(next(x for x in at.button if x.label == "新会话").disabled)
        at.run()  # A rerun must not send again.
        self.assertEqual(len(b.calls), 1)
        complete(b)
        at.run()
        self.assertFalse(at.chat_input[0].disabled)
        self.assertTrue(any("离线测试答复" in x.value for x in at.markdown))
        old = c.session_id
        next(x for x in at.button if x.label == "新会话").click().run()
        next(x for x in at.button if x.label == "取消").click().run()
        self.assertEqual(old, c.session_id)
        next(x for x in at.button if x.label == "新会话").click().run()
        next(x for x in at.button if x.label == "开始新会话").click().run()
        self.assertNotEqual(old, c.session_id)
        self.assertEqual(len(at.chat_message), 0)
        self.assertEqual(b.resets, [False])
        self.assertEqual(len(at.exception), 0)

    def test_not_found_and_unavailable_are_completed_business_results(self):
        for status, label in (("not_found", "未找到订单"), ("unavailable", "工具暂不可用")):
            at, b, c = self.make_page()
            at.chat_input[0].set_value("查一下 A9999").run()
            complete(b, events=[{"type": "tool_result", "tool": "query_order", "result": {"status": status}}])
            at.run()
            self.assertEqual(c.turns[-1]["status"], "completed")
            self.assertTrue(any(label in x.value for x in [*at.info, *at.warning]))
            self.assertEqual(len(at.error), 0)

    def test_request_failure_retry_is_a_new_attempt(self):
        at, b, c = self.make_page()
        at.chat_input[0].set_value("中文故障问题").run()
        complete(b, status="failed", error_type="APIConnectionError")
        at.run()
        self.assertTrue(any("未能取得回复" in x.value for x in at.error))
        first = c.turns[0]["request_id"]
        next(x for x in at.button if x.label == "重试此问题").click().run()
        self.assertEqual(len(b.calls), 2)
        self.assertNotEqual(first, c.turns[1]["request_id"])
        self.assertTrue(at.chat_input[0].disabled)
        self.assertEqual(len(at.exception), 0)
