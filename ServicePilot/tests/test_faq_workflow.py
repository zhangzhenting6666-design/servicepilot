"""Offline policy contract and bidirectional handoff checks; not live acceptance."""

import json
from pathlib import Path
import tempfile
import unittest

from agents import ModelSettings, RunConfig, set_tracing_disabled
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call

from scripts.order_acceptance_batch import check_case
from servicepilot.faq_data import JsonFAQSource
from servicepilot.faq_tools import build_lookup_faq_tool, lookup_faq
from servicepilot.session import OrderSession


class FAQQueryTests(unittest.TestCase):
    def test_supported_question_category_and_policy_id_return_facts(self):
        expected = {"policy_id": "RET-001", "category": "return_application",
                    "title": "模拟退货申请规则", "content": "签收后 7 天内可提出退货申请，是否通过需要人工审核。"}
        for query in ["签收后几天内可以申请退货？", "  return_application  ", "ret-001"]:
            with self.subTest(query=query):
                self.assertEqual(lookup_faq(query), {"status": "ok", "source": "local_mock", "policy": expected})

    def test_unrecorded_fees_and_payment_time_are_no_match(self):
        for query in ["退货运费谁承担？", "退款多久到账？", "退货怎么收费？", "会员优惠是什么？"]:
            with self.subTest(query=query):
                result = lookup_faq(query)
                self.assertEqual(result["status"], "no_match")
                self.assertNotIn("policy", result)

    def test_empty_question_does_not_read_source(self):
        class NeverRead:
            def find(self, query):
                raise AssertionError("Empty query must not read source")

        for query in ["", "  ", None]:
            self.assertEqual(lookup_faq(query, NeverRead())["status"], "no_match")

    def test_source_failure_is_not_no_match(self):
        with tempfile.TemporaryDirectory() as directory:
            source = JsonFAQSource(Path(directory) / "missing.json")
            self.assertEqual(lookup_faq("退货", source)["status"], "unavailable")

    def test_reads_current_file_and_rejects_broken_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policies.json"
            path.write_text(json.dumps({"source": "local_mock", "policies": [{
                "policy_id": "TEST-001", "category": "test", "title": "Test policy", "content": "Test fact",
                "match_terms": ["test"], "unsupported_terms": []}]}), encoding="utf-8")
            source = JsonFAQSource(path)
            self.assertEqual(lookup_faq("test", source)["policy"]["policy_id"], "TEST-001")
            path.write_text('{"source":"local_mock","policies":[{}]}', encoding="utf-8")
            self.assertEqual(lookup_faq("test", source)["status"], "unavailable")

    def test_sdk_schema_only_exposes_query(self):
        tool = build_lookup_faq_tool()
        self.assertEqual(tool.name, "lookup_faq")
        self.assertEqual(set(tool.params_json_schema["properties"]), {"query"})
        self.assertEqual(tool.params_json_schema["required"], ["query"])


class FAQWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        set_tracing_disabled(True)

    async def test_triage_required_choice_survives_handoff_and_run_config(self):
        def first_triage(call):
            self.assertEqual(call.model_settings.tool_choice, "required")
            return ModelStep(output=[function_call("transfer_to_faq_agent", {}, call_id="to-faq")])

        def return_to_triage(call):
            self.assertIsNone(call.model_settings.tool_choice)
            return ModelStep(output=[function_call("transfer_to_triage_agent", {}, call_id="back")])

        def second_triage(call):
            self.assertEqual(call.model_settings.tool_choice, "required")
            return ModelStep(output=[function_call("transfer_to_order_agent", {}, call_id="to-order")])

        def order_reply(call):
            self.assertIsNone(call.model_settings.tool_choice)
            return ModelStep(output=[assistant_message("模拟订单 A1001 已发货。")])

        # Responders are explicit SDK steps, not live model outputs.
        model = ScriptedModel([ModelStep(responder=step) for step in
                               (first_triage, return_to_triage, second_triage, order_reply)])
        config = RunConfig(model=model, model_settings=ModelSettings(max_tokens=1024, parallel_tool_calls=False),
                           tracing_disabled=True)
        turn = await OrderSession(config).ask("查一下 A1001")
        self.assertEqual(turn["status"], "completed", turn)

    async def test_policy_order_and_reverse_switch_use_correct_tools(self):
        def policy_reply(call):
            outputs = [item for item in call.input if isinstance(item, dict)
                       and item.get("type") == "function_call_output" and item.get("call_id") == "policy"]
            result = json.loads(outputs[0]["output"])
            self.assertEqual(result["policy"]["policy_id"], "RET-001")
            return ModelStep(output=[assistant_message("模拟政策 RET-001：签收后 7 天内可申请退货，需人工审核。")])

        def unmatched_reply(call):
            outputs = [item for item in call.input if isinstance(item, dict)
                       and item.get("type") == "function_call_output" and item.get("call_id") == "unmatched"]
            self.assertEqual(json.loads(outputs[0]["output"])["status"], "no_match")
            return ModelStep(output=[assistant_message("模拟政策没有提供退货运费规则，请向人工核实。")])

        model = ScriptedModel([
            ModelStep(output=[function_call("transfer_to_faq_agent", {}, call_id="to-faq")]),
            ModelStep(output=[function_call("lookup_faq", {"query": "签收后几天内可以申请退货？"}, call_id="policy")]),
            ModelStep(responder=policy_reply),
            ModelStep(output=[function_call("transfer_to_triage_agent", {}, call_id="faq-back")]),
            ModelStep(output=[function_call("transfer_to_order_agent", {}, call_id="to-order")]),
            ModelStep(output=[function_call("query_order", {"order_id": "A1001"}, call_id="order")]),
            ModelStep(output=[assistant_message("模拟订单 A1001：蓝牙耳机，已发货，模拟物流，MOCK1001。")]),
            ModelStep(output=[function_call("transfer_to_triage_agent", {}, call_id="order-back")]),
            ModelStep(output=[function_call("transfer_to_faq_agent", {}, call_id="to-faq-again")]),
            ModelStep(output=[function_call("lookup_faq", {"query": "退货运费谁承担？"}, call_id="unmatched")]),
            ModelStep(responder=unmatched_reply),
        ])
        session = OrderSession(RunConfig(model=model, tracing_disabled=True))
        first = await session.ask("签收后几天内可以申请退货？")
        self.assertEqual(first["status"], "completed", first)
        self.assertTrue(all(check_case({"case_id": "C01", "turns": [first]}).values()))
        second = await session.ask("再查一下 A1001")
        self.assertEqual(second["status"], "completed", second)
        self.assertTrue(all(check_case({"case_id": "C06", "turns": session.turns}).values()), session.turns)
        third = await session.ask("退货运费谁承担？")
        self.assertEqual(third["status"], "completed", third)
        self.assertEqual(third["starting_agent"], "Order Agent")
        self.assertEqual(third["final_agent"], "FAQ Agent")
        self.assertIn("签收后几天内可以申请退货", str(session.items))

    async def test_FAQ_outage_returns_unavailable_through_runner(self):
        class UnavailableFAQSource:
            def find(self, query):
                raise OSError("Synthetic policy source outage")

        model = ScriptedModel([
            ModelStep(output=[function_call("transfer_to_faq_agent", {}, call_id="transfer")]),
            ModelStep(output=[function_call("lookup_faq", {"query": "退货"}, call_id="query")]),
            ModelStep(output=[assistant_message("当前无法查询政策，请稍后重试或联系人工。")]),
        ])
        session = OrderSession(RunConfig(model=model, tracing_disabled=True), faq_source=UnavailableFAQSource())
        turn = await session.ask("退货规则是什么？")
        self.assertEqual(turn["status"], "completed", turn)
        result = next(e["result"] for e in turn["events"] if e["type"] == "tool_result")
        self.assertEqual(result["status"], "unavailable")
