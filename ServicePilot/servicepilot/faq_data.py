"""Read the local mock policy data without inferring unrecorded policies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

DEFAULT_POLICIES = Path(__file__).resolve().parents[1] / "data" / "policies.json"


class FAQSource(Protocol):
    def find(self, query: str) -> dict | None:
        """Return supported policy facts, None for no match, or raise for source failure."""
        ...


class JsonFAQSource:
    def __init__(self, path: Path = DEFAULT_POLICIES):
        self.path = path

    def find(self, query: str) -> dict | None:
        document = json.loads(self.path.read_text(encoding="utf-8"))
        if document.get("source") != "local_mock" or not isinstance(document.get("policies"), list):
            raise ValueError("Invalid policy source")
        normalized = query.casefold()
        for policy in document["policies"]:
            if not isinstance(policy, dict):
                raise ValueError("Invalid policy record")
            for field in ("policy_id", "category", "title", "content"):
                if not isinstance(policy.get(field), str) or not policy[field].strip():
                    raise ValueError("Incomplete policy record")
            for field in ("match_terms", "unsupported_terms"):
                if not isinstance(policy.get(field), list) or not all(isinstance(v, str) and v for v in policy[field]):
                    raise ValueError("Invalid policy matching terms")
            if any(term.casefold() in normalized for term in policy["unsupported_terms"]):
                continue
            if any(term.casefold() in normalized for term in policy["match_terms"]):
                return {field: policy[field] for field in ("policy_id", "category", "title", "content")}
        return None
