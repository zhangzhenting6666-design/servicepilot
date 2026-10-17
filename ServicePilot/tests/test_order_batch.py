"""Check the new acceptance harness without live model calls."""

import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from agents import RunConfig, set_tracing_disabled
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call

from scripts.order_acceptance_batch import UnavailableOrderSource, check_case, wait_for_review
from servicepilot.order_tools import query_order
from servicepilot.session import OrderSession


class BatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        set_tracing_disabled(True)

    async def test_missing_number_then_supplement_reuses_one_session(self):
        model = ScriptedModel([
            ModelStep(output=[function_call("transfer_to_order_agent", {}, call_id="transfer")]),
            ModelStep(output=[assistant_message("请提供订单号。")]),
            ModelStep(output=[function_call("query_order", {"order_id": "A1002"}, call_id="lookup")]),
            ModelStep(output=[assistant_message("模拟订单 A1002：台灯待发货，暂无物流。")]),
        ])
        session = OrderSession(RunConfig(model=model, tracing_disabled=True))
        first = await session.ask("帮我查一下订单")
        second = await session.ask("A1002")
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(second["status"], "completed", second)
        case = {"case_id": "C03", "turns": session.turns}
        self.assertTrue(all(check_case(case).values()), case)
        self.assertIn("帮我查一下订单", str(session.items))
        self.assertIn("请提供订单号", str(session.items))

    async def test_fault_is_only_injected_in_its_own_session(self):
        def unavailable_reply(call):
            tool_results = [item for item in call.input if isinstance(item, dict)
                            and item.get("type") == "function_call_output" and item.get("call_id") == "lookup"]
            self.assertEqual(json.loads(tool_results[0]["output"])["status"], "unavailable")
            return ModelStep(output=[assistant_message("当前无法查询，请稍后重试或联系人工。")])

        source = UnavailableOrderSource()
        model = ScriptedModel([
            ModelStep(output=[function_call("transfer_to_order_agent", {}, call_id="transfer")]),
            ModelStep(output=[function_call("query_order", {"order_id": "A1001"}, call_id="lookup")]),
            ModelStep(responder=unavailable_reply),
        ])
        session = OrderSession(RunConfig(model=model, tracing_disabled=True), source=source)
        turn = await session.ask("查一下 A1001")
        self.assertEqual(turn["status"], "completed", turn)
        case = {"case_id": "C08", "turns": session.turns,
                "fault_source_requested_order_ids": source.requested_order_ids}
        self.assertTrue(all(check_case(case).values()), case)
        self.assertEqual(query_order("A1001")["status"], "ok")

    async def test_review_must_target_the_current_case(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.json"
            path.write_text(json.dumps({"case_id": "C03", "verdict": "passed", "reason": "Previous case"}), encoding="utf-8")
            pending = asyncio.create_task(wait_for_review(path, "C04"))
            await asyncio.sleep(0.01)
            self.assertFalse(pending.done())
            path.write_text(json.dumps({"case_id": "C04", "verdict": "passed", "reason": "Actual reply checked"}), encoding="utf-8")
            result = await asyncio.wait_for(pending, timeout=2)
            self.assertEqual(result["case_id"], "C04")
