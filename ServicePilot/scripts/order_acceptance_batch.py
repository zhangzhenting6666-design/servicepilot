"""Test-only ordered cases, session-scoped fault injection, and reply review gates."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import uuid

from servicepilot.order_data import DEFAULT_DATA
from servicepilot.faq_data import DEFAULT_POLICIES
from servicepilot.acceptance import check_c02
from servicepilot.order_tools import query_order
from servicepilot.session import OrderSession, now

ORDER_FIRST_CASES = [
    ("C03", ["帮我查一下订单", "A1002"]),
    ("C04", ["查一下订单 ABC"]),
    ("C05", ["查一下 A9999"]),
    ("C07", ["订单 A1001 给我立即退款，不用审核"]),
    ("C08", ["查一下 A1001"]),
]

BATCH_CASES = {
    "capability": [
        ("C01", ["签收后几天内可以申请退货？"]),
        ("C06", ["签收后几天内可以申请退货？", "再查一下 A1001"]),
        ("Q01", ["帮我查 A1001 的签收日期"]),
        ("Q02", ["退货运费谁承担？"]),
    ],
    "order-first": ORDER_FIRST_CASES,
    "faq-second": [
        ("C01", ["签收后几天内可以申请退货？"]),
        ("C06", ["签收后几天内可以申请退货？", "再查一下 A1001"]),
        ("C02", ["我的订单 A1001 到哪了？"]),
        *ORDER_FIRST_CASES,
    ],
}


def has_policy_lookup(turn: dict) -> bool:
    expected = {"policy_id": "RET-001", "category": "return_application", "title": "模拟退货申请规则",
                "content": "签收后 7 天内可提出退货申请，是否通过需要人工审核。"}
    events = turn.get("events", [])
    policy_calls = [e for e in events if e["type"] == "tool_call" and e.get("tool") == "lookup_faq"
                    and isinstance(e.get("arguments"), dict)
                    and isinstance(e["arguments"].get("query"), str) and e["arguments"]["query"].strip()]
    return any(
        e["type"] == "tool_result" and e.get("tool") == "lookup_faq"
        and e.get("result") == {"status": "ok", "source": "local_mock", "policy": expected}
        and e.get("call_id") is not None
        and any(call.get("call_id") == e.get("call_id") for call in policy_calls)
        for e in events
    )


class UnavailableOrderSource:
    """A source used exclusively by the C08 test session; no file writes."""

    def __init__(self):
        self.requested_order_ids: list[str] = []

    def get(self, order_id: str) -> dict | None:
        self.requested_order_ids.append(order_id)
        raise OSError("Injected test-session source outage")


def calls(turn: dict) -> list[dict]:
    return [event for event in turn.get("events", [])
            if event["type"] == "tool_call" and event.get("tool") == "query_order"]


def outputs(turn: dict) -> list[dict]:
    return [event for event in turn.get("events", [])
            if event["type"] == "tool_result" and event.get("tool") == "query_order"]


def has_lookup(turn: dict, order_id: str, status: str, order: dict | None = None) -> bool:
    matching_calls = [event for event in calls(turn) if event.get("arguments") == {"order_id": order_id}]
    return any(
        event.get("result", {}).get("status") == status
        and (order is None or event["result"].get("order") == order)
        and event.get("call_id") is not None
        and any(call.get("call_id") == event.get("call_id") for call in matching_calls)
        for event in outputs(turn)
    )


def check_case(case: dict) -> dict[str, bool]:
    """Check execution facts only; the final natural-language reply needs review."""
    turns = case["turns"]
    checks = {"all_turns_completed": bool(turns) and all(t["status"] == "completed" for t in turns),
              "fresh_session": bool(turns) and turns[0]["starting_agent"] == "Triage Agent"}
    case_id = case["case_id"]
    if case_id == "C01":
        checks.update(actual_policy_lookup=bool(turns) and has_policy_lookup(turns[0]),
                      final_agent_FAQ=bool(turns) and turns[0].get("final_agent") == "FAQ Agent")
    elif case_id == "C06":
        expected = {"order_id": "A1001", "product": "蓝牙耳机", "status": "已发货",
                    "carrier": "模拟物流", "tracking_number": "MOCK1001"}
        second_events = turns[1].get("events", []) if len(turns) == 2 else []
        checks.update(
            two_turns_same_session=len(turns) == 2,
            first_turn_actual_policy_lookup=bool(turns) and has_policy_lookup(turns[0]),
            first_turn_final_agent_FAQ=bool(turns) and turns[0].get("final_agent") == "FAQ Agent",
            second_turn_starts_from_FAQ=len(turns) == 2 and turns[1]["starting_agent"] == "FAQ Agent",
            FAQ_back_to_triage=any(e["type"] == "handoff" and e.get("source_agent") == "FAQ Agent"
                                   and e.get("target_agent") == "Triage Agent" for e in second_events),
            triage_to_order=any(e["type"] == "handoff" and e.get("source_agent") == "Triage Agent"
                                and e.get("target_agent") == "Order Agent" for e in second_events),
            second_turn_queries_A1001=len(turns) == 2 and has_lookup(turns[1], "A1001", "ok", expected),
        )
    elif case_id == "C02":
        checks.update(check_c02(turns[0]) if turns else {"has_turn": False})
    elif case_id == "C03":
        expected = {"order_id": "A1002", "product": "台灯", "status": "待发货",
                    "carrier": None, "tracking_number": None}
        checks.update(
            two_turns_same_session=len(turns) == 2,
            no_lookup_without_order_number=bool(turns) and not calls(turns[0]),
            second_turn_keeps_current_agent=len(turns) == 2 and turns[1]["starting_agent"] == turns[0].get("final_agent"),
            query_A1002_after_supplement=len(turns) == 2 and has_lookup(turns[1], "A1002", "ok", expected),
        )
    elif case_id == "C04":
        # The agent may reject the format before querying; any actual lookup must reject it too.
        checks["no_successful_or_wrong_order_lookup"] = bool(turns) and (
            not calls(turns[0]) or (
                all(e.get("arguments") == {"order_id": "ABC"} for e in calls(turns[0]))
                and len(outputs(turns[0])) == len(calls(turns[0]))
                and all(e.get("result", {}).get("status") == "invalid_input" for e in outputs(turns[0]))
            )
        )
    elif case_id == "C05":
        checks["query_A9999_not_found"] = bool(turns) and has_lookup(turns[0], "A9999", "not_found")
    elif case_id == "C07":
        checks["read_only_tools"] = all(
            event.get("tool") in {"query_order", "lookup_faq"} for turn in turns for event in turn.get("events", [])
            if event["type"] == "tool_call")
        checks["optional_lookup_only_A1001"] = all(
            event.get("arguments") == {"order_id": "A1001"} for turn in turns for event in calls(turn))
    elif case_id == "C08":
        checks.update(
            actual_query_unavailable=bool(turns) and has_lookup(turns[0], "A1001", "unavailable"),
            no_repeat_lookup=bool(turns) and len(calls(turns[0])) == 1,
            no_successful_tool_result=all(e.get("result", {}).get("status") == "unavailable"
                                         for turn in turns for e in outputs(turn)),
            session_fault_source_invoked=case.get("fault_source_requested_order_ids") == ["A1001"],
        )
    elif case_id == "Q01":
        checks["no_receipt_field_in_results"] = all(
            set(e.get("result", {}).get("order", {})) <= {"order_id", "product", "status", "carrier", "tracking_number"}
            for turn in turns for e in outputs(turn))
    elif case_id == "Q02":
        checks["actual_policy_no_match"] = any(
            e["type"] == "tool_result" and e.get("tool") == "lookup_faq"
            and e.get("result", {}).get("status") == "no_match"
            for turn in turns for e in turn.get("events", []))
    else:
        raise ValueError("Unknown acceptance case")
    return checks


async def wait_for_review(control: Path, case_id: str) -> dict:
    """Wait for the local developer's verdict, with no model calls while waiting."""
    while True:
        if control.exists():
            try:
                review = json.loads(control.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                review = {}
            if (review.get("case_id") == case_id and review.get("verdict") in {"passed", "failed"}
                    and isinstance(review.get("reason"), str) and review["reason"].strip()):
                return review
        await asyncio.sleep(1)


async def run_batch(args, config, report: dict, path: Path, key: str, save, show) -> int:
    selected = [case for case in BATCH_CASES[args.batch] if not args.case or case[0] == args.case]
    if not selected:
        raise ValueError("The selected case does not belong to this batch")
    if args.first_case:
        first = [case for case in selected if case[0] == args.first_case]
        if not first:
            raise ValueError("The priority case is not in the selected batch")
        selected = first + [case for case in selected if case[0] != args.first_case]
    initial_hash = hashlib.sha256(DEFAULT_DATA.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    initial_policy_hash = hashlib.sha256(DEFAULT_POLICIES.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    control = path.with_suffix(".review-control.json")
    report.update(batch=args.batch, review_gate=args.review_gate,
                  review_control_file=str(control), mock_data_hash_before=initial_hash,
                  mock_policy_hash_before=initial_policy_hash)
    for case_id, questions in selected:
        fault_source = UnavailableOrderSource() if case_id == "C08" else None
        session = OrderSession(config, source=fault_source)
        case = {"case_id": case_id, "session_id": uuid.uuid4().hex, "fresh_session": True,
                "turns": session.turns, "verdict": "running",
                "fault_injection": "unavailable_source_in_this_session_only" if fault_source else None}
        report["sessions"].append(case)
        report["status"] = "running"
        save(path, report, key)
        for question in questions:
            print(f"\n{case_id} / 会话 {case['session_id']}：{question}", flush=True)
            turn = await session.ask(question)
            show(turn, key)
            save(path, report, key)
            if turn["status"] != "completed":
                break
        if fault_source is not None:
            case["fault_source_requested_order_ids"] = fault_source.requested_order_ids
        case["checks"] = check_case(case)
        case["verdict"] = "pending_reply_review"
        report["status"] = "awaiting_reply_review" if args.review_gate else "running"
        save(path, report, key)
        if args.review_gate:
            print(f"{case_id} 已保存，等待本地开发复核答复；无需在本窗口输入。", flush=True)
            review = await wait_for_review(control, case_id)
            case["reply_review"] = review
            case["verdict"] = review["verdict"]
            if not all(case["checks"].values()):
                case["verdict"] = "failed"
            save(path, report, key)
        elif not all(case["checks"].values()):
            case["verdict"] = "failed"
        if case["verdict"] == "failed":
            report["status"] = "failed"
            return 1
    final_hash = hashlib.sha256(DEFAULT_DATA.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    report["mock_data_hash_after"] = final_hash
    report["mock_data_unchanged"] = initial_hash == final_hash
    report["mock_policy_hash_after"] = hashlib.sha256(DEFAULT_POLICIES.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    report["mock_policies_unchanged"] = initial_policy_hash == report["mock_policy_hash_after"]
    report["normal_source_query_after_batch"] = query_order("A1001")
    healthy = (report["mock_data_unchanged"] and report["mock_policies_unchanged"]
               and report["normal_source_query_after_batch"].get("status") == "ok")
    all_passed = all(case["verdict"] == "passed" for case in report["sessions"])
    report["status"] = ("reviewed_passed" if healthy and all_passed else
                        "automatic_checks_passed_pending_review" if healthy else "failed")
    return 0 if healthy else 1
