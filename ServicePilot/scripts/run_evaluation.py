"""Run predefined real evaluations, preserve rounds and freeze before holdout."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

PRODUCT = Path(__file__).resolve().parents[1]
WORKSPACE = PRODUCT.parent
sys.path.insert(0, str(PRODUCT))
from run_deepseek_customer_service import read_key
from run_order_customer_service import save, show
from order_acceptance_batch import wait_for_review
from servicepilot.evaluation import DEFAULT_MANIFEST, TestFAQSource, TestOrderSource, check_step, load_manifest
from servicepilot.model_config import BASE_URL, MODEL, create_client_config
from servicepilot.session import OrderSession, now

ARTIFACTS = PRODUCT / "artifacts/evaluation"


def fingerprint(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def version_evidence():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=WORKSPACE, text=True).strip()
    paths = [*sorted((PRODUCT / "servicepilot").glob("*.py")), *sorted((PRODUCT / "data").glob("*.json")),
             DEFAULT_MANIFEST, Path(__file__).resolve(), PRODUCT / "scripts/run_order_customer_service.py",
             PRODUCT / "scripts/order_acceptance_batch.py", PRODUCT / "scripts/run_deepseek_customer_service.py",
             PRODUCT / "requirements.lock.txt"]
    return {"commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
            "worktree_dirty": bool(git("status", "--porcelain")),
            "hash_mode": "SHA256 after CRLF to LF normalization",
            "source_hashes": {str(p.relative_to(WORKSPACE)).replace("\\", "/"): fingerprint(p) for p in paths},
            "dependencies": {name: importlib.metadata.version(name) for name in ("openai", "openai-agents")}}


def assert_unchanged(version):
    mismatched = [rel for rel, expected in version["source_hashes"].items()
                  if not (WORKSPACE / rel).is_file() or fingerprint(WORKSPACE / rel) != expected]
    if mismatched:
        raise RuntimeError("EvaluationSourceDrift")


def next_round(field):
    rounds = []
    for p in ARTIFACTS.glob("eval-run-*.json"):
        if p.name.endswith(".review-control.json"):
            continue
        r = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(r.get(field), int):
            rounds.append(r[field])
    return max(rounds, default=0) + 1


def metrics(cases):
    turns = [t for c in cases for t in c["turns"]]
    return {"cases_executed": len(cases), "turns": len(turns),
            "passed": sum(c.get("verdict") == "passed" for c in cases),
            "failed": sum(c.get("verdict") == "failed" for c in cases),
            "pending_review": sum(c.get("verdict") == "pending_reply_review" for c in cases),
            "model_request_events": sum(e["type"] == "model_request" for t in turns for e in t["events"]),
            "usage_available_turns": sum("usage" in t for t in turns),
            "usage_incomplete": any("usage" not in t for t in turns),
            "usage": {key: sum(t.get("usage", {}).get(key, 0) for t in turns)
                      for key in ("requests", "input_tokens", "output_tokens", "total_tokens")}}


async def run_case(definition, config, manifest, report, path, key, gate, version):
    started = time.perf_counter()
    case = {"case_id": definition["id"], "split": definition["split"], "definition": copy.deepcopy(definition),
            "started_at": now(), "version": copy.deepcopy(version), "turns": [], "checks": {}, "verdict": "running"}
    report["cases"].append(case)
    sessions = {}
    for index, step in enumerate(definition["steps"], 1):
        assert_unchanged(version)
        name = step.get("session", "main")
        if name not in sessions:
            order_source, faq_source = TestOrderSource(), TestFAQSource()
            session = OrderSession(config, source=order_source, faq_source=faq_source)
            entry = {"case_id": definition["id"], "name": name, "session_id": uuid.uuid4().hex,
                     "fresh_session": True, "turns": session.turns}
            sessions[name] = (session, order_source, faq_source, entry)
            report["sessions"].append(entry)
        session, order_source, faq_source, entry = sessions[name]
        action = step.get("fault_before")
        if action == "order_unavailable":
            order_source.available = False
        elif action == "faq_unavailable":
            faq_source.available = False
        order_start, faq_start = len(order_source.accesses), len(faq_source.accesses)
        report["status"] = "running_" + definition["split"]
        save(path, report, key)
        print(f"\n{definition['id']} / {name} / 第{index}步：{step['input']}", flush=True)
        turn = await session.ask(step["input"])
        turn.update(step_number=index, session_id=entry["session_id"], session_name=name,
                    fault_state_before={"orders_available": order_source.available, "faq_available": faq_source.available},
                    source_accesses={"orders": copy.deepcopy(order_source.accesses[order_start:]),
                                     "faq": copy.deepcopy(faq_source.accesses[faq_start:])})
        case["turns"].append(turn)
        show(turn, key)
        for name, passed in check_step(step, turn, manifest["facts"]).items():
            case["checks"][f"step{index}_{name}"] = passed
        if len(session.turns) == 1:
            case["checks"][f"step{index}_new_session_starts_triage"] = turn["starting_agent"] == "Triage Agent"
        save(path, report, key)
        if turn["status"] != "completed":
            case["checks"]["all_planned_steps_executed"] = False
            break
    case.update(finished_at=now(), elapsed_seconds=round(time.perf_counter() - started, 3),
                verdict="pending_reply_review")
    case["checks"]["all_planned_steps_executed"] = len(case["turns"]) == len(definition["steps"])
    report.update(status="awaiting_reply_review", current_case_id=definition["id"])
    save(path, report, key)
    if gate:
        print("已保存本次答复，等待开发助手复核；本窗口无需输入。", flush=True)
        review = await wait_for_review(Path(report["review_control_file"]), definition["id"])
        case["reply_review"] = review
        case["verdict"] = review["verdict"] if all(case["checks"].values()) else "failed"
    elif not all(case["checks"].values()):
        case["verdict"] = "failed"
    save(path, report, key)


def valid_development_freeze(report):
    cases = [c for c in report.get("cases", []) if c["split"] == "development"]
    return len(cases) == 15 and all(c["verdict"] == "passed" and all(c["checks"].values()) for c in cases)


async def run(args, key, manifest, report, path):
    client, config = create_client_config(key)
    selected = [c for c in manifest["cases"] if not args.case or c["id"] == args.case]
    async with client:
        if args.split in {"both", "development"}:
            report["development_round"] = next_round("development_round")
            for definition in selected:
                if definition["split"] == "development":
                    await run_case(definition, config, manifest, report, path, key, args.review_gate, report["version"])
            report["development_metrics"] = metrics([c for c in report["cases"] if c["split"] == "development"])
            save(path, report, key)
            if args.split == "development" or not valid_development_freeze(report):
                report["status"] = "development_reviewed_passed" if valid_development_freeze(report) else "development_needs_review_or_repair"
                return 0 if valid_development_freeze(report) else 1
            report["status"] = "awaiting_version_freeze"
            save(path, report, key)
            print("开发集15/15通过；等待保存版本并确认FREEZE，再运行留出集。", flush=True)
            review = await wait_for_review(Path(report["review_control_file"]), "FREEZE")
            report["freeze_review"] = review
            if review["verdict"] != "passed":
                report["status"] = "freeze_rejected"
                return 1
            frozen = version_evidence()
            assert_unchanged(report["version"])
            if review.get("frozen_commit") != frozen["commit"]:
                raise RuntimeError("FrozenCommitMismatch")
        else:
            baseline = json.loads(Path(args.freeze_from).read_text(encoding="utf-8"))
            if not valid_development_freeze(baseline):
                raise ValueError("Freeze baseline must contain 15 reviewed development passes")
            assert_unchanged(baseline["version"])
            frozen = version_evidence()
            report["freeze_from"] = str(Path(args.freeze_from).resolve())
        report["frozen_version"] = frozen
        report["holdout_round"] = next_round("holdout_round")
        save(path, report, key)
        for definition in selected:
            if definition["split"] == "holdout":
                # Continue all fixed holdout cases even if a reply fails. No tuning during this round.
                assert_unchanged(frozen)
                await run_case(definition, config, manifest, report, path, key, args.review_gate, frozen)
        report["holdout_metrics"] = metrics([c for c in report["cases"] if c["split"] == "holdout"])
        report["status"] = "reviewed_passed" if report["holdout_metrics"]["passed"] == 10 else "holdout_has_failures_or_pending_review"
        return 0 if report["status"] == "reviewed_passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["both", "development", "holdout"], default="development")
    parser.add_argument("--review-gate", action="store_true")
    parser.add_argument("--case", help="Selective development regression; cannot claim a full split pass")
    parser.add_argument("--freeze-from", help="A previous record containing all 15 reviewed development passes")
    args = parser.parse_args()
    if args.split == "both" and (not args.review_gate or args.case):
        parser.error("both requires review-gate and the full fixed list")
    if args.split == "holdout" and (not args.freeze_from or args.case):
        parser.error("holdout requires freeze-from and all ten cases")
    manifest = load_manifest()
    if args.case and not any(c["id"] == args.case and c["split"] == "development" for c in manifest["cases"]):
        parser.error("Only predefined development cases can be selected")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    stamp = now().replace(":", "").replace("+", "_")
    path = ARTIFACTS / f"eval-run-{stamp}-{uuid.uuid4().hex[:8]}.json"
    report = {"started_at": now(), "status": "awaiting_credentials", "evidence_kind": "live_backend_evaluation",
              "version": version_evidence(), "manifest_sha256": fingerprint(DEFAULT_MANIFEST),
              "manifest": manifest, "model": MODEL, "base_url": BASE_URL,
              "settings": {"thinking": "disabled", "max_tokens": 1024, "parallel_tool_calls": False,
                           "http_retries": 0, "http_timeout_seconds": 45, "max_turns_per_question": 6,
                           "triage_tool_choice": "required", "triage_reset_tool_choice": False},
              "python_executable": sys.executable, "python_version": sys.version.split()[0],
              "launch_argv": [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), *sys.argv[1:]],
              "sessions": [], "cases": [], "api_request_attempted": False,
              "review_control_file": str(path.with_suffix(".review-control.json")),
              "normal_data_hashes_before": {p.name: fingerprint(p) for p in (PRODUCT / "data").glob("*.json")}}
    key = ""
    try:
        save(path, report, key)
        print("ServicePilot真实评测。仅在本窗口隐藏输入密钥；不把密钥发送到聊天。", flush=True)
        key = read_key(force_prompt=True)
        return asyncio.run(run(args, key, manifest, report, path))
    except (KeyboardInterrupt, EOFError):
        report["status"] = "cancelled"
        return 130
    except Exception as error:
        report.update(status="run_failed", error_type=type(error).__name__, http_status=getattr(error, "status_code", None))
        print(f"评测运行失败：{type(error).__name__}。原始异常未显示或保存。", flush=True)
        return 1
    finally:
        report["normal_data_hashes_after"] = {p.name: fingerprint(p) for p in (PRODUCT / "data").glob("*.json")}
        report["normal_data_unchanged"] = report["normal_data_hashes_before"] == report["normal_data_hashes_after"]
        report["finished_at"] = now()
        report["observed_metrics"] = metrics(report["cases"])
        save(path, report, key)
        print(f"评测证据：{path}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
