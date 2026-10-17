"""Build or check the fixed public source snapshot. Never reads Secrets or raw logs."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from servicepilot.source_catalog import PUBLIC_FILES, SNAPSHOT, content_hash, load_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = {}
    for name in PUBLIC_FILES:
        text = (PRODUCT / name).read_text(encoding="utf-8")
        # Fail closed on common literal credential assignments and token formats.
        if re.search(r"\bsk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9_.-]{12,}", text):
            raise ValueError("Credential-like value in public file: " + name)
        if re.search(r'''(?i)(?:api_key|DEEPSEEK_API_KEY)\s*=\s*["'][^"']{12,}["']''', text):
            raise ValueError("Literal credential-like assignment in public file: " + name)
        files[name] = {"text": text, "sha256": content_hash(text), "line_count": len(text.splitlines())}
    if args.check:
        snapshot = load_snapshot()
        assert snapshot["files"] == files, "Public source changed; rebuild snapshot before release"
    else:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PRODUCT.parent, text=True).strip()
        hashes = {name: item["sha256"] for name, item in files.items()}
        snapshot = {"release_label": "代码解读 · 展示版 r5", "parent_workspace_commit": revision,
                    "version_note": "Content-addressed product snapshot, not a claim that the parent commit contains these changes. Release commit is recorded separately.",
                    "snapshot_id": content_hash(json.dumps(hashes, sort_keys=True, separators=(",", ":"))),
                    "text_mode": "UTF-8 with LF newlines; full contents, no redaction or elision",
                    "files": files}
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "files": len(files), "checked": args.check,
                      "api_request_attempted": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
