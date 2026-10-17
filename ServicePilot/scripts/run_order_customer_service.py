"""Run ServicePilot's real DeepSeek order workflow and save redacted evidence."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

PRODUCT = Path(__file__).resolve().parents[1]
WORKSPACE = PRODUCT.parent
sys.path.insert(0, str(PRODUCT))

from run_deepseek_customer_service import BASE_URL, MODEL, read_key, redact
from servicepilot.acceptance import check_c02
from servicepilot.evidence_io import atomic_write_text
from servicepilot.session import OrderSession, now


def version_evidence() -> dict:
    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", *arguments], cwd=WORKSPACE, text=True).strip()

    files = [*sorted((PRODUCT / "servicepilot").glob("*.py")), *sorted((PRODUCT / "data").glob("*.json")),
             Path(__file__).resolve(), PRODUCT / "scripts/run_deepseek_customer_service.py",
             PRODUCT / "scripts/order_acceptance_batch.py"]
    return {"commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
            "worktree_dirty": bool(git("status", "--porcelain")),
            "hash_mode": "SHA256 after CRLF to LF normalization",
            "business_source_hashes": {str(p.relative_to(WORKSPACE)).replace("\\", "/"):
                                       hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                                       for p in files}}


def save(path: Path, report: dict, key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report["api_request_attempted"] = any(
        event["type"] == "model_request" for session in report.get("sessions", [])
        for turn in session["turns"] for event in turn["events"])
    payload = redact(json.dumps(report, ensure_ascii=False, indent=2), key) + "\n"
    atomic_write_text(path, payload)


def show(turn: dict, key: str) -> None:
    for event in turn["events"]:
        if event["type"] == "handoff":
            print(f"转交：{event['source_agent']} → {event['target_agent']}")
        elif event["type"] in {"tool_call", "tool_result"}:
            print(redact(json.dumps(event, ensure_ascii=False), key))
    if turn["status"] == "completed":
        print(redact(f"{turn['final_agent']}：{turn['final_answer']}", key))
        print(f"本轮模型请求：{turn['usage']['requests']} 次")
    else:
        print(f"运行失败：{turn['error_type']}，HTTP {turn.get('http_status')}；没有保存原始错误响应。")


async def run(args, key: str, report: dict, path: Path) -> int:
    from servicepilot.model_config import create_client_config

    client, config = create_client_config(key)
    async with client:
        if args.batch:
            from order_acceptance_batch import run_batch

            return await run_batch(args, config, report, path, key, save, show)
        if args.acceptance:
            cases = [("C02", "我的订单 A1001 到哪了？"), ("C02-paraphrase", "A1001 发货了吗？")]
            if args.primary_only:
                cases = cases[:1]
            for case_id, question in cases:
                session = OrderSession(config)
                case = {"case_id": case_id, "session_id": uuid.uuid4().hex, "fresh_session": True,
                        "turns": session.turns, "verdict": "running"}
                report["sessions"].append(case)
                print(f"\n新会话 {case_id}：{question}", flush=True)
                turn = await session.ask(question)
                show(turn, key)
                case["checks"] = check_c02(turn)
                case["verdict"] = "pending_reply_review" if all(case["checks"].values()) else "failed"
                save(path, report, key)
                if case["verdict"] == "failed":
                    report["status"] = "failed"
                    return 1
            report["status"] = "automatic_checks_passed_pending_review"
            print("\n真实路径自动检查通过；仍需核对最终答复是否存在无依据的额外承诺。")
            return 0

        session = OrderSession(config)
        report["sessions"].append({"case_id": "manual", "session_id": uuid.uuid4().hex,
                                    "fresh_session": True, "turns": session.turns})
        while True:
            question = args.question if args.question is not None else input("请输入问题（exit 退出）： ")
            if question.strip().lower() in {"exit", "quit", "退出"}:
                report["status"] = "finished"
                return 0
            if not question.strip():
                continue
            turn = await session.ask(question)
            show(turn, key)
            save(path, report, key)
            if turn["status"] == "failed":
                report["status"] = "failed"
                return 1
            if args.question is not None:
                report["status"] = "completed"
                return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-key", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--acceptance", action="store_true", help="Run C02 and a paraphrase in fresh sessions.")
    mode.add_argument("--question", help="Send one user question through the actual model workflow.")
    mode.add_argument("--batch", choices=["order-first", "faq-second", "capability"], help="Run an acceptance batch; capability checks unsupported receipt dates.")
    parser.add_argument("--primary-only", action="store_true", help="Only run the primary C02 acceptance case.")
    parser.add_argument("--case", choices=["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"], help="Select one batch case for a retest.")
    parser.add_argument("--first-case", choices=["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"], help="Review a failed case first, then continue the rest of the batch.")
    parser.add_argument("--review-gate", action="store_true", help="Pause after each batch case for local reply review.")
    args = parser.parse_args()
    if args.primary_only and not args.acceptance:
        parser.error("--primary-only requires --acceptance")
    if (args.case or args.first_case or args.review_gate) and not args.batch:
        parser.error("--case, --first-case and --review-gate require --batch")
    if args.case and args.first_case and args.case != args.first_case:
        parser.error("--case and --first-case must match when both are supplied")
    if args.batch == "order-first" and any(value and value not in {"C03", "C04", "C05", "C07", "C08"}
                                          for value in (args.case, args.first_case)):
        parser.error("The selected case does not belong to order-first")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    stamp = now().replace(":", "").replace("+", "_")
    path = PRODUCT / "artifacts" / "orders" / f"order-run-{stamp}-{uuid.uuid4().hex[:8]}.json"
    report = {"started_at": now(), "status": "awaiting_credentials", "evidence_kind": "live_api",
              "api_request_attempted": False, "model": MODEL, "base_url": BASE_URL,
              "settings": {"thinking": "disabled", "max_tokens": 1024,
                           "parallel_tool_calls": False, "max_turns_per_question": 6,
                           "http_retries": 0, "http_timeout_seconds": 45,
                           "triage_tool_choice": "required", "triage_reset_tool_choice": False},
              "python_executable": sys.executable, "python_version": sys.version.split()[0],
              "launch_argv": [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), *sys.argv[1:]],
              "version": version_evidence(), "sessions": []}
    key = ""
    try:
        print("ServicePilot：本地模拟订单与政策；回答由真实 DeepSeek API 生成。", flush=True)
        print("请仅在本窗口的 DeepSeek API key: 提示后粘贴密钥，输入显示星号。", flush=True)
        save(path, report, key)
        key = read_key(force_prompt=args.fresh_key)
        report["status"] = "running"
        return asyncio.run(run(args, key, report, path))
    except (KeyboardInterrupt, EOFError):
        report["status"] = "cancelled"
        print("已退出。")
        return 130
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__,
                      http_status=getattr(error, "status_code", None))
        print(f"运行失败：{type(error).__name__}；原始异常未输出，避免暴露凭据。")
        return 1
    finally:
        report["finished_at"] = now()
        report["api_request_attempted"] = any(
            event["type"] == "model_request" for session in report["sessions"]
            for turn in session["turns"] for event in turn["events"])
        save(path, report, key)
        print(f"证据已保存（密钥已脱敏）：{path}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
