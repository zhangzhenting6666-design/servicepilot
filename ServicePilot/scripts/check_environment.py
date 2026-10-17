"""Save current environment facts and unauthenticated reachability, never secrets."""
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from importlib.metadata import version

import agents
from agents.models.default_models import get_default_model, get_default_model_settings

from day1_support import EVIDENCE, ROOT

record = {
    "checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    "platform": platform.platform(),
    "python_version": sys.version,
    "python_executable": sys.executable,
    "venv_prefix": sys.prefix,
    "base_prefix": sys.base_prefix,
    "venv_isolated": sys.prefix != sys.base_prefix,
    "agents_import_path": agents.__file__,
    "packages": {name: version(name) for name in ("pip", "openai-agents", "openai", "pydantic", "mcp")},
    "git_path": shutil.which("git"),
    "git_version": subprocess.run(["git", "--version"], capture_output=True, text=True, check=True).stdout.strip(),
    "credential_presence_process_only": {
        name: bool(os.environ.get(name, "").strip())
        for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_DEFAULT_MODEL")
    },
    "sdk_default_model": get_default_model(),
    "sdk_default_model_settings": get_default_model_settings().to_json_dict(),
    "official_source": json.loads((EVIDENCE / "official-source.json").read_text(encoding="utf-8-sig")),
    "note": "API reachability probe has no Authorization header and is NOT an authenticated model call.",
}
try:
    with urllib.request.urlopen("https://api.openai.com/v1/models", timeout=15) as response:
        record["unauthenticated_api_probe"] = {"http_status": response.status}
except urllib.error.HTTPError as exc:
    record["unauthenticated_api_probe"] = {"http_status": exc.code}
except Exception as exc:
    record["unauthenticated_api_probe"] = {"error_type": type(exc).__name__}
EVIDENCE.mkdir(parents=True, exist_ok=True)
(EVIDENCE / "environment.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, ensure_ascii=False, indent=2))
