"""Inspect the named real browser sessions; preserve raw records and review provenance."""
import hashlib
import json
from pathlib import Path
import sys

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from servicepilot.session import now


def main():
    prefixes = ["975d38f0", "161f3ff6", "2f018bf2", "f170b401"]
    sessions = []
    requests = tokens = 0
    mismatches = []
    for prefix in prefixes:
        matches = list((PRODUCT / "artifacts/web").glob("web-session-" + prefix + "*.json"))
        if len(matches) != 1:
            raise RuntimeError("Expected exactly one specified session")
        path = matches[0]
        raw = json.loads(path.read_text(encoding="utf-8"))
        for relative, expected in raw["version"]["source_hashes"].items():
            source = PRODUCT.parent / relative
            actual = hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            if actual != expected:
                mismatches.append(relative)
        turns = raw["turns"]
        if not all(t.get("status") == "completed" for t in turns):
            raise RuntimeError("Browser run contains unfinished or failed turns")
        requests += sum(t.get("usage", {}).get("requests", 0) for t in turns)
        tokens += sum(t.get("usage", {}).get("total_tokens", 0) for t in turns)
        sessions.append({"raw_file": str(path.relative_to(PRODUCT)),
                         "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "session_id": raw["session_id"], "previous_session_id": raw.get("previous_session_id"),
                         "created_at": raw["created_at"], "version": raw["version"], "turns": turns})
    report = {"reviewed_at": now(), "evidence_kind": "real_browser_workbench_source_review",
              "browser_url": "http://127.0.0.1:8501", "model": "deepseek-flash",
              "requests": requests, "total_tokens": tokens, "user_turns": sum(len(s["turns"]) for s in sessions),
              "source_hash_mismatches": sorted(set(mismatches)), "sessions": sessions,
              "not_a_cloud_test": True, "not_a_25_case_rerun": True}
    destination = PRODUCT / "artifacts/workbench/live-review.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_hash_mismatches": report["source_hash_mismatches"], "requests": requests,
                      "tokens": tokens, "user_turns": report["user_turns"], "turns": [
                          {"input": t["input"], "answer": t["final_answer"],
                           "handoffs": [{"from": e["source_agent"], "to": e["target_agent"]} for e in t["events"] if e["type"] == "handoff"],
                           "results": [e["result"] for e in t["events"] if e["type"] == "tool_result"]
                          } for s in sessions for t in s["turns"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
