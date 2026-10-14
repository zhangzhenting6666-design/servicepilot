"""Evidence checks for C02; semantic review of the actual reply is still required."""

import re


def check_c02(turn: dict) -> dict[str, bool]:
    events = turn.get("events", [])
    calls = [e for e in events if e["type"] == "tool_call" and e.get("tool") == "query_order"]
    outputs = [e for e in events if e["type"] == "tool_result" and e.get("tool") == "query_order"]
    expected = {"order_id": "A1001", "product": "蓝牙耳机", "status": "已发货",
                "carrier": "模拟物流", "tracking_number": "MOCK1001"}
    matched_calls = [e for e in calls if e.get("arguments") == {"order_id": "A1001"}]
    has_result = any(e.get("result") == {"status": "ok", "source": "local_mock", "order": expected}
                     and any(c.get("call_id") == e.get("call_id") for c in matched_calls)
                     for e in outputs)
    answer = turn.get("final_answer", "")
    estimate = re.search(r"20\d{2}[年/-]|(?:预计|大约|大概|保证|将于|会在).{0,15}(?:明天|后天|\d+\s*[天日小时])", answer)
    return {
        "completed": turn.get("status") == "completed",
        "fresh_session": turn.get("starting_agent") == "Triage Agent",
        "triage_to_order": any(e["type"] == "handoff" and e.get("source_agent") == "Triage Agent"
                               and e.get("target_agent") == "Order Agent" for e in events),
        "query_order_A1001_called": bool(matched_calls),
        "actual_tool_result_matches_mock": has_result,
        "final_agent_order": turn.get("final_agent") == "Order Agent",
        "answer_contains_expected_facts": all(value in answer for value in expected.values()),
        "answer_identifies_mock": "模拟" in answer,
        "no_obvious_delivery_estimate": estimate is None,
    }
