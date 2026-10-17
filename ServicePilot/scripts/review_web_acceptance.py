"""Verify saved E01 execution facts; manual verdicts refer to inspected live UI replies."""
import hashlib
import json
from pathlib import Path
import sys

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from order_acceptance_batch import check_case, has_lookup, calls
from servicepilot.session import now

ROOT = PRODUCT / "artifacts/web"
MAPPING = {
    "C01": ("8746642b", "实际 RET-001；7天内可申请，人工审核，不保证获批，无签收时间查询承诺。"),
    "C02": ("5e26e43c", "实际 query_order(A1001)；蓝牙耳机、已发货、模拟物流、MOCK1001；未编到货日期。"),
    "C03": ("a2ae35c7", "先追问且未查订单；同一会话补充A1002后返回台灯、待发货、暂无物流。连续两次Enter仅一轮提交。"),
    "C04": ("dc99537d", "Order说明ABC格式错误并要求更正；没有工具调用或其他订单事实。"),
    "C05": ("1d3263fd", "实际not_found；答复未找到并建议核对编号，没有说成服务故障。"),
    "C06": ("8010c6f7", "先查FAQ，后FAQ→Triage→Order并查A1001；两轮政策与订单事实正确，无签收日期推断。"),
    "C07": ("47963130", "实际只读查A1001；明确无法直接退款、不能跳过审核，未声称已退款/提交审核/接通人工/建单。"),
    "C08": ("720cc2b8", "会话级故障，实际query_order(A1001)一次→unavailable；答复当前无法查询，未使用旧事实。"),
}


def load_prefix(prefix):
    files = list(ROOT.glob(f"web-session-{prefix}*.json"))
    if len(files) != 1:
        raise ValueError(f"Expected one evidence file for {prefix}")
    p = files[0]
    return p, json.loads(p.read_text(encoding="utf-8"))


def main():
    reviewed = []
    observations = json.loads((ROOT / "browser-observations.json").read_text(encoding="utf-8"))
    for case_id, (prefix, reason) in MAPPING.items():
        p, r = load_prefix(prefix)
        case = {"case_id": case_id, "turns": r["turns"]}
        if case_id == "C08":
            checks = {"completed": r["turns"][0]["status"] == "completed",
                      "fresh_triage": r["turns"][0]["starting_agent"] == "Triage Agent",
                      "session_fault_configured": r["fault_injection"] == "this_session_order_source_unavailable",
                      "actual_query_unavailable": has_lookup(r["turns"][0], "A1001", "unavailable"),
                      "one_query_only": len(calls(r["turns"][0])) == 1}
        else:
            checks = check_case(case)
        checks["web_live_api_evidence"] = r["evidence_kind"] == "web_live_api" and r["api_request_attempted"]
        checks["reply_and_events_observed_on_page"] = any(o["name"] == "e01-" + case_id.lower()
                and f"会话 {prefix}" in o["state"] for o in observations)
        checks["no_running_or_blank_answer"] = all(t["status"] == "completed" and t.get("final_answer", "").strip() for t in r["turns"])
        mismatches = []
        for rel, expected in r["version"]["source_hashes"].items():
            actual = hashlib.sha256((PRODUCT.parent / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            if actual != expected:
                mismatches.append(rel)
        checks["current_source_matches_tested_hashes"] = not mismatches
        reviewed.append({"case_id": case_id, "verdict": "passed" if all(checks.values()) else "failed",
                         "checks": checks, "source_mismatches": mismatches,
                         "manual_reply_review": {"reviewer": "developer", "reason": reason, "reviewed_at": now()},
                         "raw_file": str(p.relative_to(PRODUCT)).replace("\\", "/"),
                         "raw_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                         "session_id": r["session_id"], "page_id": r["page_id"],
                         "version": r["version"], "usage": {name: sum(t.get("usage", {}).get(name, 0) for t in r["turns"])
                                                   for name in ("requests", "total_tokens")}})
    _, normal = load_prefix("ebd8ed43")
    _, isolated = load_prefix("3d2be93a")
    _, c03 = load_prefix("a2ae35c7")
    normal_checks = {"normal_query_after_fault": has_lookup(normal["turns"][0], "A1001", "ok"),
                     "fault_cleared": normal["fault_injection"] is None,
                     "different_page_ids": normal["page_id"] != isolated["page_id"],
                     "other_page_asks_number_without_lookup": len(isolated["turns"]) == 1
                         and not calls(isolated["turns"][0]) and "订单号" in isolated["turns"][0]["final_answer"],
                     "blank_and_multiline_draft_did_not_request": len(isolated["turns"]) == 1,
                     "double_enter_did_not_duplicate_first_turn": len(c03["turns"]) == 2,
                     "reset_did_not_inherit_A1001": c03["previous_session_id"].startswith("5e26e43c")
                         and not calls(c03["turns"][0]),
                     "narrow_viewport_confirmed": any(o["name"] == "e01-narrow-confirmed-390"
                         and o["viewport"]["width"] == o["viewport"]["scrollWidth"] == 390 for o in observations)}
    passed = sum(c["verdict"] == "passed" for c in reviewed)
    summary = {"reviewed_at": now(), "evidence_kind": "live_web_reply_review",
               "status": "reviewed_passed" if passed == 8 and all(normal_checks.values()) else "failed",
               "passed": passed, "total_core_cases": 8, "cases": reviewed,
               "core_usage": {name: sum(c["usage"][name] for c in reviewed) for name in ("requests", "total_tokens")},
               "extra_browser_checks": normal_checks,
               "extra_live_sessions": [normal["session_id"], isolated["session_id"]],
               "browser_observations": "artifacts/web/browser-observations.json",
               "limitations": ["处理中禁用输入和重置；不支持等待期间编辑草稿或取消后台请求",
                   "中文内容输入及Shift+Enter已检查；Windows中文输入法候选字组合态Enter尚未人工验收",
                   "请求连接失败、空答复、重试与迟到响应防线使用离线替身检查；本轮真实故障为C08工具不可用",
                   "25条评测、长会话、其他设备、登录和部署未完成"],
               "preserved_initial_smoke_session": "7981c61b600f490f9132fed7da2855e0",
               "initial_smoke_is_excluded_from_final_core_count": True}
    (ROOT / "e01-web-review-2026-10-14.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "passed": passed,
                      "failed_checks": {c["case_id"]: [k for k, v in c["checks"].items() if not v] for c in reviewed if c["verdict"] != "passed"},
                      "extras": normal_checks, "usage": summary["core_usage"]}, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "reviewed_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
