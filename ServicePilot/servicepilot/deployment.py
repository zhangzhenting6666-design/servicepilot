"""Service-side bootstrap and bounded public demo usage; never stores credentials."""
import os
import threading


class DemoBusyError(RuntimeError):
    pass


class DemoQuotaError(RuntimeError):
    pass


class DemoLimiter:
    def __init__(self, max_concurrent=3, max_requests=120):
        self.max_concurrent = max_concurrent
        self.max_requests = max_requests
        self.active = 0
        self.accepted = 0
        self.lock = threading.Lock()

    def reserve(self):
        with self.lock:
            if self.accepted >= self.max_requests:
                raise DemoQuotaError("Demo request limit")
            if self.active >= self.max_concurrent:
                raise DemoBusyError("Demo concurrency limit")
            self.active += 1
            self.accepted += 1

    def release(self):
        with self.lock:
            self.active -= 1


_bootstrap_lock = threading.Lock()


def bootstrap_from_environment():
    from .web_runtime import configure_server, server_ready
    if server_ready():
        return
    with _bootstrap_lock:
        if server_ready():
            return
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        options = {}
        if not key:
            import streamlit as st
            try:
                key = str(st.secrets.get("DEEPSEEK_API_KEY", "")).strip()
                options = {name: st.secrets.get(name) for name in
                           ("DEMO_MAX_CONCURRENT", "DEMO_MAX_REQUESTS")}
            except (FileNotFoundError, KeyError):
                return
        if not key or any(ord(c) < 32 for c in key):
            return
        def bounded(name, default, maximum):
            try:
                return max(1, min(maximum, int(os.environ.get(name) or options.get(name) or default)))
            except (TypeError, ValueError):
                return default
        configure_server(key, hosted=True, limiter=DemoLimiter(
            bounded("DEMO_MAX_CONCURRENT", 3, 10), bounded("DEMO_MAX_REQUESTS", 120, 1000)))
