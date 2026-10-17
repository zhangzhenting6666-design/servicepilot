"""Offline evaluation guard checks; never substitutes for real model evaluation."""
import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest

from agents import RunConfig, set_tracing_disabled
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from servicepilot.evaluation import TestFAQSource, TestOrderSource, check_step, load_manifest
from servicepilot.session import OrderSession
from scripts.run_evaluation import assert_unchanged, fingerprint, valid_development_freeze


class EvaluationTests(unittest.TestCase):
    def test_manifest_sessions_whitespace_and_predefined_splits(self):
        manifest = load_manifest()
        cases = {c["id"]: c for c in manifest["cases"]}
        self.assertEqual(cases["HOLD03"]["steps"][1]["input"], "  a1002  ")
        self.assertEqual([s["session"] for s in cases["DEV11"]["steps"]], ["A", "B"])
        self.assertEqual(cases["HOLD10"]["steps"][1]["fault_before"], "order_unavailable")

    def test_tool_success_without_correlated_call_or_wrong_order_is_rejected(self):
        facts = load_manifest()["facts"]
        step = {"expect": {"kind": "order", "order_id": "A1001"}}
        turn = {"status": "completed", "final_answer": "unit", "events": [
            {"type": "tool_result", "tool": "query_order", "call_id": "orphan",
             "result": {"status": "ok", "source": "local_mock", "order": facts["orders"]["A1001"]}}]}
        self.assertFalse(all(check_step(step, turn, facts).values()))
        turn["events"].insert(0, {"type": "tool_call", "tool": "query_order", "call_id": "orphan", "arguments": {"order_id": "A1002"}})
        self.assertFalse(check_step(step, turn, facts)["no_other_order_queried"])

    def test_freeze_rejects_drift_and_partial_or_pending_development(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "unit.txt"
            p.write_text("before", encoding="utf-8")
            version = {"source_hashes": {str(p): fingerprint(p)}}
            assert_unchanged(version)
            p.write_text("changed", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                assert_unchanged(version)
        report = {"cases": [{"split": "development", "verdict": "passed", "checks": {"unit": True}} for _ in range(14)]}
        self.assertFalse(valid_development_freeze(report))
        report["cases"].append({"split": "development", "verdict": "pending_reply_review", "checks": {"unit": True}})
        self.assertFalse(valid_development_freeze(report))
        report["cases"][-1]["verdict"] = "passed"
        self.assertTrue(valid_development_freeze(report))


class MutableFaultTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_session_success_then_source_failure_and_FAQ_outage(self):
        set_tracing_disabled(True)
        source = TestOrderSource()
        model = ScriptedModel([
            ModelStep(output=[function_call("transfer_to_order_agent", {}, call_id="h")]),
            ModelStep(output=[function_call("query_order", {"order_id": "A1001"}, call_id="q1")]),
            ModelStep(output=[assistant_message("offline first")]),
            ModelStep(output=[function_call("query_order", {"order_id": "A1001"}, call_id="q2")]),
            ModelStep(output=[assistant_message("offline unavailable")]),
        ])
        session = OrderSession(RunConfig(model=model, tracing_disabled=True), source=source)
        first = await session.ask("查A1001")
        source.available = False
        second = await session.ask("再查A1001")
        self.assertEqual([a["available"] for a in source.accesses], [True, False])
        result = next(e["result"] for e in second["events"] if e["type"] == "tool_result")
        self.assertEqual(result["status"], "unavailable")
        second["source_accesses"] = {"orders": source.accesses[-1:]}
        step = {"expect": {"kind": "order_unavailable", "order_id": "A1001"}}
        self.assertTrue(all(check_step(step, second, load_manifest()["facts"]).values()))
        self.assertIn("offline first", str(session.items))
        faq = TestFAQSource()
        faq.available = False
        with self.assertRaises(OSError):
            faq.find("退货")
        self.assertFalse(faq.accesses[-1]["available"])
