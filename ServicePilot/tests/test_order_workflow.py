"""Offline regression checks; scripted model steps are not live acceptance evidence."""

import json
from pathlib import Path
import tempfile
import unittest

from agents import RunConfig, set_tracing_disabled
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call

from servicepilot.acceptance import check_c02
from servicepilot.order_data import JsonOrderSource
from servicepilot.order_tools import build_query_order_tool, query_order
from servicepilot.session import OrderSession


class QueryTests(unittest.TestCase):
    def test_order_facts_and_normalization(self):
        result = query_order("  a1001  ")
        self.assertEqual(result, {"status": "ok", "source": "local_mock", "order": {
            "order_id": "A1001", "product": "蓝牙耳机", "status": "已发货",
            "carrier": "模拟物流", "tracking_number": "MOCK1001"}})

    def test_invalid_numbers_do_not_access_source(self):
        class NeverRead:
            def get(self, order_id):
                raise AssertionError("Invalid input must not access the source")

        for value in ["ABC", "A10001", "A１００１", "我的订单 A1001 到哪了？", "", None]:
            with self.subTest(value=value):
                self.assertEqual(query_order(value, NeverRead())["status"], "invalid_input")

    def test_not_found_is_distinct_from_source_failure(self):
        self.assertEqual(query_order("A9999")["status"], "not_found")
        with tempfile.TemporaryDirectory() as temporary:
            source = JsonOrderSource(Path(temporary) / "missing.json")
            self.assertEqual(query_order("A1001", source)["status"], "unavailable")

    def test_other_records_have_no_invented_logistics(self):
        for order_id, status in [("A1002", "待发货"), ("A1003", "已取消")]:
            result = query_order(order_id)
            self.assertEqual(result["order"]["status"], status)
            self.assertIsNone(result["order"]["carrier"])
            self.assertIsNone(result["order"]["tracking_number"])

    def test_source_can_be_replaced(self):
        class ReplacementSource:
            def __init__(self):
                self.seen = []

            def get(self, order_id):
                self.seen.append(order_id)
                return {"order_id": order_id, "product": "替换源商品", "status": "待发货",
                        "carrier": None, "tracking_number": None}

        source = ReplacementSource()
        result = query_order(" a1004 ", source)
        self.assertEqual(source.seen, ["A1004"])
        self.assertEqual(result["order"]["product"], "替换源商品")

    def test_each_query_reads_current_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "orders.json"
            path.write_text(json.dumps({"source": "local_mock", "orders": {
                "A1001": {"order_id": "A1001", "product": "测试商品", "status": "待发货",
                          "carrier": None, "tracking_number": None}}}), encoding="utf-8")
            source = JsonOrderSource(path)
            self.assertEqual(query_order("A1001", source)["status"], "ok")
            path.write_text("invalid-json", encoding="utf-8")
            self.assertEqual(query_order("A1001", source)["status"], "unavailable")

    def test_tool_schema_only_exposes_order_number(self):
        tool = build_query_order_tool()
        self.assertEqual(tool.name, "query_order")
        self.assertEqual(set(tool.params_json_schema["properties"]), {"order_id"})
        self.assertEqual(tool.params_json_schema["required"], ["order_id"])


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        set_tracing_disabled(True)

    async def test_runner_handoff_tool_result_and_history(self):
        def final_response(call):
            outputs = [item for item in call.input if isinstance(item, dict)
                       and item.get("type") == "function_call_output"]
            payloads = [json.loads(item["output"]) for item in outputs if item.get("call_id") == "order-1"]
            self.assertEqual(payloads[0]["order"]["tracking_number"], "MOCK1001")
            return ModelStep(output=[assistant_message("模拟订单 A1001：蓝牙耳机已发货，模拟物流，MOCK1001。")])

        model = ScriptedModel([
            ModelStep(output=[function_call("transfer_to_order_agent", {}, call_id="handoff-1")]),
            ModelStep(output=[function_call("query_order", {"order_id": "A1001"}, call_id="order-1")]),
            ModelStep(responder=final_response),
            ModelStep(output=[function_call("query_order", {"order_id": "A1002"}, call_id="order-2")]),
            ModelStep(output=[assistant_message("模拟订单 A1002：台灯待发货，暂无物流。")]),
        ])
        session = OrderSession(RunConfig(model=model, tracing_disabled=True))
        first = await session.ask("我的订单 A1001 到哪了？")
        self.assertEqual(first["status"], "completed", first)
        self.assertTrue(all(check_c02(first).values()), first)
        second = await session.ask("改查 A1002")
        self.assertEqual(second["status"], "completed", second)
        self.assertEqual(second["starting_agent"], "Order Agent")
        tool_result = next(e for e in second["events"] if e["type"] == "tool_result")
        self.assertEqual(tool_result["result"]["order"]["order_id"], "A1002")
        self.assertIn("我的订单 A1001 到哪了？", str(session.items))
        fresh = OrderSession(RunConfig(model=ScriptedModel(), tracing_disabled=True))
        self.assertEqual(fresh.items, [])
        self.assertEqual(fresh.current_agent.name, "Triage Agent")

    async def test_failed_model_attempt_keeps_evidence(self):
        model = ScriptedModel([ModelStep(error=RuntimeError("synthetic test error"))])
        session = OrderSession(RunConfig(model=model, tracing_disabled=True))
        result = await session.ask("查 A1001")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertNotIn("final_answer", result)
        self.assertEqual(result["events"][0]["type"], "model_request")
        self.assertEqual(session.items, [])
