"""Read-only order data source, replaceable without changing the tool contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data" / "orders.json"


class OrderSource(Protocol):
    def get(self, order_id: str) -> dict | None:
        """Return one order, None when absent, or raise when the source is unavailable."""
        ...


class JsonOrderSource:
    def __init__(self, path: Path = DEFAULT_DATA):
        self.path = path

    def get(self, order_id: str) -> dict | None:
        # Read on every call so a previous lookup cannot hide a current source failure.
        document = json.loads(self.path.read_text(encoding="utf-8"))
        if document.get("source") != "local_mock" or not isinstance(document.get("orders"), dict):
            raise ValueError("Invalid mock data source")
        order = document["orders"].get(order_id)
        if order is None:
            return None
        fields = {"order_id", "product", "status", "carrier", "tracking_number"}
        if not isinstance(order, dict) or not fields.issubset(order):
            raise ValueError("Incomplete order record")
        if order["order_id"] != order_id or not isinstance(order["product"], str):
            raise ValueError("Invalid order identity")
        if order["status"] not in {"已发货", "待发货", "已取消"}:
            raise ValueError("Invalid order status")
        for field in ("carrier", "tracking_number"):
            if order[field] is not None and not isinstance(order[field], str):
                raise ValueError("Invalid logistics field")
        # Expose only the agreed facts, with no inferred delivery date.
        return {field: order[field] for field in sorted(fields)}
