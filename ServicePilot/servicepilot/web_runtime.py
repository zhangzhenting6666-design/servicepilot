"""Per-page backend, stable async loop, submission ownership and safe evidence."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import tempfile
import uuid
import weakref

from .model_config import BASE_URL, MODEL, create_client_config
from .evidence_io import atomic_write_text
from .session import OrderSession, now

PRODUCT = Path(__file__).resolve().parents[1]
_server = None  # Key exists only in this process; never Streamlit widgets or disk.


def safe_text(text: str, key: str = "") -> str:
    if key:
        text = text.replace(key, "[密钥已隐藏]")
    return re.sub(r"(?i)\b(?:sk-[A-Za-z0-9_-]+|Bearer\s+[^\s\"']+)", "[密钥已隐藏]", text)


def web_version() -> dict:
    workspace = PRODUCT.parent
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=workspace, text=True).strip()
    files = [*sorted((PRODUCT / "servicepilot").glob("*.py")),
             *sorted((PRODUCT / "data").glob("*.json")), PRODUCT / "app.py",
             PRODUCT / "scripts/run_web.py", PRODUCT / "requirements.lock.txt",
             PRODUCT / "requirements.txt", PRODUCT / "assets/workbench.css"]
    try:
        revision = {"commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
                    "worktree_dirty": bool(git("status", "--porcelain"))}
    except (FileNotFoundError, subprocess.CalledProcessError):
        revision = {"commit": None, "branch": None, "worktree_dirty": None,
                    "version_note": "Git metadata unavailable; source hashes identify this runtime"}
    return {**revision,
            "hash_mode": "SHA256 after CRLF to LF normalization",
            "source_hashes": {str(p.relative_to(workspace)).replace("\\", "/"):
                              hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in files if p.exists()},
            "dependencies": {name: importlib.metadata.version(name)
                             for name in ("streamlit", "openai", "openai-agents")},
            "python_executable": sys.executable, "python_version": sys.version.split()[0]}


def configure_server(key: str, acceptance_controls=False, port=8501, *, hosted=False, limiter=None):
    global _server
    _server = {"key": key, "acceptance_controls": acceptance_controls and not hosted,
               "hosted": hosted, "limiter": limiter, "version": web_version(),
               "launch_argv": [sys.executable, "-X", "utf8", str(PRODUCT / "scripts/run_web.py"),
                               "--port", str(port), *(["--acceptance-controls"] if acceptance_controls else [])]}


def server_ready() -> bool:
    return _server is not None


def acceptance_enabled() -> bool:
    return bool(_server and _server["acceptance_controls"])


class UnavailableSource:
    def get(self, order_id):
        raise OSError("Test-session-only order source outage")


class SessionBackend:
    """Every page owns its client, executor, async loop and OrderSession."""
    def __init__(self, key, limiter=None):
        self.limiter = limiter
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="servicepilot-page")
        self.runner = asyncio.Runner()
        self.pool.submit(self._init, key).result()
        self._cleanup = weakref.finalize(self, self._dispose, self.pool, self.runner, self.client)

    def _init(self, key):
        async def create():
            self.client, self.config = create_client_config(key)
            self.session = OrderSession(self.config)
        self.runner.run(create())

    @staticmethod
    def _dispose(pool, runner, client):
        def close():
            try:
                runner.run(client.close())
            finally:
                runner.close()
        pool.submit(close)
        pool.shutdown(wait=False)

    def ask(self, question):
        if self.limiter is not None:
            try:
                self.limiter.reserve()
            except Exception as error:
                from concurrent.futures import Future
                future = Future()
                future.set_exception(error)
                return future
        def execute():
            try:
                return self.runner.run(self.session.ask(question))
            finally:
                if self.limiter is not None:
                    self.limiter.release()
        try:
            return self.pool.submit(execute)
        except Exception:
            if self.limiter is not None:
                self.limiter.release()
            raise

    def reset(self, fault=False):
        def replace():
            self.session = OrderSession(self.config, source=UnavailableSource() if fault else None)
        self.pool.submit(replace).result()

    def close(self):
        self._cleanup()


class PageConversation:
    def __init__(self, backend, *, key="", version=None, evidence_dir=None, launch_argv=None,
                 evidence_kind="offline_test"):
        self.backend = backend
        self._key = key
        self.version = version or {}
        self.evidence_dir = evidence_dir
        self.launch_argv = launch_argv or []
        self.evidence_kind = evidence_kind
        self.page_id = uuid.uuid4().hex
        self.lock = threading.RLock()
        self.pending = None
        self.seen_ids = set()
        self.last_submission = None
        self._fresh()

    def _fresh(self, parent=None, fault=False):
        self.session_id = uuid.uuid4().hex
        self.turns = []
        self.report = {"evidence_kind": self.evidence_kind, "page_id": self.page_id,
                       "session_id": self.session_id, "previous_session_id": parent,
                       "created_at": now(), "version": self.version, "model": MODEL, "base_url": BASE_URL,
                       "launch_argv": self.launch_argv, "turns": self.turns,
                       "fault_injection": "this_session_order_source_unavailable" if fault else None,
                       "controls": [], "api_request_attempted": False}
        self._save()

    @property
    def busy(self):
        return self.pending is not None

    def _save(self):
        if self.evidence_dir is None:
            return
        self.report["api_request_attempted"] = any(e["type"] == "model_request"
            for t in self.turns for e in t.get("events", []))
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        path = self.evidence_dir / f"web-session-{self.session_id}.json"
        atomic_write_text(path, safe_text(json.dumps(self.report, ensure_ascii=False, indent=2), self._key) + "\n")

    def submit(self, question, request_id, owner, *, retry=False):
        with self.lock:
            question = safe_text(question, self._key).strip()
            reason = None
            if owner != self.session_id:
                reason = "旧会话的提交已忽略"
            elif self.busy:
                reason = "当前问题正在处理，请等待"
            elif not question:
                reason = "请输入问题"
            elif request_id in self.seen_ids:
                reason = "重复提交已忽略"
            elif (not retry and self.last_submission and self.last_submission[0] == question
                  and time.monotonic() - self.last_submission[1] < 2):
                reason = "重复提交已忽略"
            if reason:
                self.report["controls"].append({"time": now(), "action": "submission_rejected", "reason": reason})
                self._save()
                return reason
            self.seen_ids.add(request_id)
            self.last_submission = (question, time.monotonic())
            turn = {"request_id": request_id, "session_id": owner, "input": question,
                    "status": "running", "events": [], "submitted_at": now()}
            future = self.backend.ask(question)
            self.turns.append(turn)
            self.pending = (future, owner, turn)
            self._save()
            return None

    def collect(self):
        with self.lock:
            if not self.pending or not self.pending[0].done():
                return False
            future, owner, turn = self.pending
            try:
                result = future.result()
                result = json.loads(safe_text(json.dumps(result, ensure_ascii=False), self._key))
                if result.get("status") == "completed" and not result.get("final_answer", "").strip():
                    result.update(status="failed", error_type="EmptyResponse")
            except Exception as error:
                result = {"status": "failed", "error_type": type(error).__name__, "events": []}
            if owner == self.session_id and turn in self.turns:
                turn.update(result)
            else:
                self.report["controls"].append({"time": now(), "action": "stale_response_ignored"})
            self.pending = None
            self._save()
            return True

    def reset(self, fault=False):
        with self.lock:
            if self.busy:
                return "正在处理中，完成后才能开始新会话"
            try:
                self.backend.reset(fault)
            except Exception:
                return "新会话未能创建，请重试"
            parent = self.session_id
            self.report["reset_at"] = now()
            self._save()
            self.last_submission = None
            self._fresh(parent, fault)
            return None


def new_conversation():
    if _server is None:
        raise RuntimeError("Use the local masked-key launcher")
    evidence_dir = (Path(os.environ.get("SERVICEPILOT_EVIDENCE_DIR") or
                         str(Path(tempfile.gettempdir()) / "servicepilot-events"))
                    if _server.get("hosted") else PRODUCT / "artifacts/web")
    return PageConversation(SessionBackend(_server["key"], _server.get("limiter")), key=_server["key"],
                            version=_server["version"], evidence_dir=evidence_dir,
                            launch_argv=_server["launch_argv"], evidence_kind="web_live_api")
