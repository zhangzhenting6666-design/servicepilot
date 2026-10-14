"""Parameterized, read-only order lookup and its SDK tool adapter."""

from __future__ import annotations

import json
import re

from agents import FunctionTool, function_tool

from .order_data import JsonOrderSource, OrderSource


def query_order(order_id: str, source: OrderSource | None = None) -> dict:
    """Normalize and validate an order number, then return structured lookup facts."""
    if not isinstance(order_id, str):
        return {"status": "invalid_input", "message": "订单号应为 A 加四位数字，例如 A1001。"}
    normalized = order_id.strip().upper()
    if re.fullmatch(r"A[0-9]{4}", normalized) is None:
        return {"status": "invalid_input", "message": "订单号应为 A 加四位数字，例如 A1001。"}
    try:
        order = (source if source is not None else JsonOrderSource()).get(normalized)
    except (OSError, ValueError, TypeError, AttributeError):
        return {"status": "unavailable", "order_id": normalized, "message": "当前无法查询订单，请稍后重试或联系人工。"}
    if order is None:
        return {"status": "not_found", "order_id": normalized, "message": "未找到该订单，请核对订单号。"}
    return {"status": "ok", "source": "local_mock", "order": order}


def build_query_order_tool(source: OrderSource | None = None) -> FunctionTool:
    @function_tool(name_override="query_order", strict_mode=False)
    async def lookup(order_id: str) -> str:
        """查询本地模拟订单。传入订单号，例如 A1001；不要传入完整用户问题。

        Args:
            order_id: 用户提供的订单号，工具会去除首尾空格、转为大写并校验格式。
        """
        return json.dumps(query_order(order_id, source), ensure_ascii=False)

    return lookup
