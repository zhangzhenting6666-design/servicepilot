"""Atomic evidence writes with bounded retries for Windows reader sharing locks."""
from pathlib import Path
import time
import uuid


def atomic_write_text(path: Path, payload: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        for attempt in range(8):
            try:
                temporary.replace(path)
                return
            except PermissionError as error:
                # A concurrent local reader can temporarily deny replace on Windows.
                # This retries only the disk write, never the model/API request.
                if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 7:
                    raise
                time.sleep(min(0.025 * 2 ** attempt, 0.2))
    finally:
        temporary.unlink(missing_ok=True)
