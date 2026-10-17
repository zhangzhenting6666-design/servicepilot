"""Run bounded local tests and save evidence clearly labeled offline."""

import json
from pathlib import Path
import sys
import unittest
import uuid

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from servicepilot.session import now

suite = unittest.defaultTestLoader.discover(str(PRODUCT / "tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
record = {"time": now(), "evidence_kind": "offline_unit_and_scripted_model_tests",
          "api_request_attempted": False, "tests_run": result.testsRun,
          "failures": len(result.failures), "errors": len(result.errors),
          "status": "passed" if result.wasSuccessful() else "failed",
          "scope": "Local query contract and SDK orchestration; not C02 live API acceptance",
          "launch_argv": [sys.executable, "-X", "utf8", str(Path(__file__).resolve())]}
stamp = now().replace(":", "").replace("+", "_")
path = PRODUCT / "artifacts" / "orders" / f"local-check-{stamp}-{uuid.uuid4().hex[:8]}.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"离线检查证据：{path}")
raise SystemExit(0 if result.wasSuccessful() else 1)
