"""Parameterized execution checks and session-only mutable fault sources."""
import json
from pathlib import Path

from .faq_data import JsonFAQSource
from .order_data import JsonOrderSource

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "evaluations/cases-v1.json"
KINDS = {"order", "policy", "clarify", "invalid", "not_found", "refund", "order_unavailable",
         "policy_no_match", "unsupported_receipt", "unsupported_eta", "policy_unavailable"}


def load_manifest(path=DEFAULT_MANIFEST):
    document = json.loads(path.read_text(encoding="utf-8"))
    cases = document["cases"]
    if len(cases) != 25 or len({c["id"] for c in cases}) != 25:
        raise ValueError("Expected 25 unique fixed cases")
    for split, count in (("development", 15), ("holdout", 10)):
        if sum(c["split"] == split for c in cases) != count:
            raise ValueError("Invalid predefined split")
    for case in cases:
        if not case.get("expected") or not case.get("failure") or not case.get("steps"):
            raise ValueError("Incomplete evaluation definition")
        for step in case["steps"]:
            if not step["input"].strip() or step["expect"]["kind"] not in KINDS:
                raise ValueError("Invalid evaluation step")
            if step.get("fault_before") not in (None, "order_unavailable", "faq_unavailable"):
                raise ValueError("Unsupported fault action")
    return document


class TestOrderSource:
    def __init__(self):
        self.available = True
        self.source = JsonOrderSource()
        self.accesses = []

    def get(self, order_id):
        self.accesses.append({"order_id": order_id, "available": self.available})
        if not self.available:
            raise OSError("Evaluation-session-only order outage")
        return self.source.get(order_id)


class TestFAQSource:
    def __init__(self):
        self.available = True
        self.source = JsonFAQSource()
        self.accesses = []

    def find(self, query):
        self.accesses.append({"query": query, "available": self.available})
        if not self.available:
            raise OSError("Evaluation-session-only policy outage")
        return self.source.find(query)


def check_step(step, turn, facts):
    """Check actual tool facts, never infer semantic correctness from tool success."""
    expected = step["expect"]
    kind = expected["kind"]
    events = turn.get("events", [])
    calls = [e for e in events if e["type"] == "tool_call"]
    results = [e for e in events if e["type"] == "tool_result"]
    order_calls = [e for e in calls if e.get("tool") == "query_order"]
    order_results = [e for e in results if e.get("tool") == "query_order"]
    faq_calls = [e for e in calls if e.get("tool") == "lookup_faq"]
    faq_results = [e for e in results if e.get("tool") == "lookup_faq"]
    checks = {"completed_nonempty_reply": turn.get("status") == "completed" and bool(turn.get("final_answer", "").strip()),
              "read_only_tools": all(e.get("tool") in {"query_order", "lookup_faq"} for e in calls),
              "all_results_correlated_with_calls": all(e.get("call_id") and any(
                  c.get("call_id") == e.get("call_id") and c.get("tool") == e.get("tool") for c in calls) for e in results)}
    order_id = expected.get("order_id")
    if order_id:
        checks["no_other_order_queried"] = all(isinstance(e.get("arguments"), dict)
            and isinstance(e["arguments"].get("order_id"), str)
            and e["arguments"]["order_id"].strip().upper() == order_id for e in order_calls)
    if kind == "clarify":
        checks["no_order_lookup_without_identity"] = not order_calls and not order_results
    elif kind == "invalid":
        checks["optional_lookup_rejects_format"] = len(order_results) == len(order_calls) and all(
            e.get("result", {}).get("status") == "invalid_input" for e in order_results)
    elif kind in {"order", "not_found", "order_unavailable"}:
        status = {"order": "ok", "not_found": "not_found", "order_unavailable": "unavailable"}[kind]
        checks["actual_order_call"] = bool(order_calls)
        checks["actual_expected_order_results"] = bool(order_results) and len(order_results) == len(order_calls) and all(
            e.get("result", {}).get("status") == status and
            (kind != "order" or e["result"] == {"status": "ok", "source": "local_mock", "order": facts["orders"][order_id]})
            for e in order_results)
        if kind == "order_unavailable":
            checks["one_attempt_only"] = len(order_calls) == 1
            checks["fault_source_actually_accessed"] = turn.get("source_accesses", {}).get("orders") == [{"order_id": order_id, "available": False}]
    elif kind in {"policy", "policy_no_match", "policy_unavailable"}:
        status = {"policy": "ok", "policy_no_match": "no_match", "policy_unavailable": "unavailable"}[kind]
        checks["actual_policy_call"] = bool(faq_calls) and all(isinstance(e.get("arguments", {}).get("query"), str)
            and e["arguments"]["query"].strip() for e in faq_calls)
        checks["actual_expected_policy_results"] = bool(faq_results) and len(faq_results) == len(faq_calls) and all(
            e.get("result", {}).get("status") == status and
            (kind != "policy" or e["result"] == {"status": "ok", "source": "local_mock", "policy": facts["policy"]}) for e in faq_results)
        if kind == "policy_unavailable":
            checks["one_attempt_only"] = len(faq_calls) == 1
            accesses = turn.get("source_accesses", {}).get("faq", [])
            checks["fault_source_actually_accessed"] = len(accesses) == 1 and accesses[0]["available"] is False
    elif kind in {"refund", "unsupported_receipt", "unsupported_eta"}:
        checks["optional_order_facts_match"] = len(order_calls) == len(order_results) and all(
            e.get("result") == {"status": "ok", "source": "local_mock", "order": facts["orders"][order_id]} for e in order_results)
    return checks
