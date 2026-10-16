"""Read a fixed, verified public source snapshot as data; never import or execute it."""
import hashlib
import json
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[1] / "assets/code-guide/snapshot.json"

# Explicit public product list; no filesystem glob, user path, logs or Secrets.
PUBLIC_FILES = (
    "app.py", "servicepilot/__init__.py", "servicepilot/agent_config.py",
    "servicepilot/model_config.py", "servicepilot/order_tools.py", "servicepilot/order_data.py",
    "servicepilot/faq_tools.py", "servicepilot/faq_data.py", "servicepilot/session.py",
    "servicepilot/web_runtime.py", "servicepilot/workbench_ui.py", "servicepilot/deployment.py",
    "servicepilot/evidence_io.py", "servicepilot/acceptance.py", "servicepilot/evaluation.py",
    "servicepilot/source_catalog.py", "servicepilot/code_guide.py", "data/orders.json",
    "data/policies.json", "assets/workbench.css", "requirements.txt", ".streamlit/config.toml",
)


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_snapshot():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if set(snapshot["files"]) != set(PUBLIC_FILES):
        raise ValueError("Unexpected public file list")
    hashes = {}
    for name in PUBLIC_FILES:
        item = snapshot["files"][name]
        hashes[name] = content_hash(item["text"])
        if hashes[name] != item["sha256"] or len(item["text"].splitlines()) != item["line_count"]:
            raise ValueError("Snapshot integrity mismatch")
    expected = content_hash(json.dumps(hashes, sort_keys=True, separators=(",", ":")))
    if expected != snapshot["snapshot_id"]:
        raise ValueError("Snapshot version mismatch")
    return snapshot


def source_file(snapshot, name):
    if name not in PUBLIC_FILES:
        raise ValueError("File not in the public list")
    return snapshot["files"][name]


def excerpt(snapshot, name, first, last):
    """Select real lines within the same full-file snapshot; no handwritten excerpts."""
    text = source_file(snapshot, name)["text"]
    lines = text.splitlines()
    position = text.index(first)
    if text.find(first, position + 1) != -1:
        raise ValueError("Ambiguous excerpt anchor")
    start = text.count("\n", 0, position)
    end_position = text.index(last, position) + len(last)
    end = text.count("\n", 0, end_position)
    return {"start": start + 1, "end": end + 1, "text": "\n".join(lines[start:end + 1])}
