"""Small local evidence helpers for Day 1; no mock model or secret logging."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts" / "day1"
SHANGHAI = timezone(timedelta(hours=8))


def redact(text: str) -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        text = text.replace(key, "[REDACTED]")
    return re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", text)


def metadata(target: str, model: str, prompt: str) -> dict:
    return {
        "target": target,
        "started_at": datetime.now(SHANGHAI).isoformat(),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "sdk_version": version("openai-agents"),
        "openai_version": version("openai"),
        "model_requested": model,
        "input": prompt,
        "credential_present": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "provider": "OpenAI official endpoint",
        "status": "started",
        "real_call_succeeded": False,
        "usage": None,
        "tracing_export_enabled": False,
    }


def configure_client() -> None:
    from openai import AsyncOpenAI
    from agents import set_default_openai_client, set_tracing_disabled

    # Day 1 uses the official endpoint. Fail before sending a credential to a custom URL.
    if os.environ.get("OPENAI_BASE_URL", "").strip() not in ("", "https://api.openai.com/v1", "https://api.openai.com/v1/"):
        raise ValueError("custom_endpoint_not_verified")
    set_tracing_disabled(True)
    set_default_openai_client(AsyncOpenAI(timeout=30.0, max_retries=0))


def failure(record: dict, exc: Exception) -> None:
    # API error messages may echo part of a credential; keep typed, useful fields only.
    code = getattr(exc, "code", None)
    allowed = {"insufficient_quota", "invalid_api_key", "model_not_found", "rate_limit_exceeded"}
    record.update(
        status="failed",
        error_type=type(exc).__name__,
        http_status=getattr(exc, "status_code", None),
        error_code=code if code in allowed else None,
        reason="See local API setup and troubleshooting steps; raw exception omitted to protect credentials.",
    )


def save(record: dict, output: str = "") -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    record["finished_at"] = datetime.now(SHANGHAI).isoformat()
    record["stdout"] = redact(output)
    stamp = datetime.now(SHANGHAI).strftime("%Y%m%d-%H%M%S-%f")
    filename = f"{record['target']}-{stamp}.json"
    content = redact(json.dumps(record, ensure_ascii=False, indent=2)) + "\n"
    (EVIDENCE / filename).write_text(content, encoding="utf-8")
    (EVIDENCE / f"{record['target']}-latest.json").write_text(content, encoding="utf-8")
    print(f"{record['target']}: {record['status']}")
    print(f"Evidence: {EVIDENCE / filename}")
    if output:
        print(redact(output))
    if record.get("reason"):
        print(record["reason"])
