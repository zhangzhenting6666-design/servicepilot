"""Policy lookup returns facts and a policy identifier, rather than a final reply."""

from __future__ import annotations

import json

from agents import FunctionTool, function_tool

from .faq_data import FAQSource, JsonFAQSource


def lookup_faq(query: str, source: FAQSource | None = None) -> dict:
    if not isinstance(query, str) or not query.strip():
        return {"status": "no_match", "message": "没有找到有依据的模拟政策，请补充问题。"}
    try:
        policy = (source if source is not None else JsonFAQSource()).find(query.strip())
    except (OSError, ValueError, TypeError, AttributeError):
        return {"status": "unavailable", "message": "当前无法查询模拟政策，请稍后重试或联系人工。"}
    if policy is None:
        return {"status": "no_match", "message": "未收录该问题的模拟政策，不能据此提供规则；建议联系人工核实。"}
    return {"status": "ok", "source": "local_mock", "policy": policy}


def build_lookup_faq_tool(source: FAQSource | None = None) -> FunctionTool:
    @function_tool(name_override="lookup_faq", strict_mode=False)
    async def lookup(query: str) -> str:
        """查询模拟售后政策，返回政策编号与内容。未收录问题和查询故障分别返回 no_match 与 unavailable。

        Args:
            query: 用户的完整政策问题或政策类别，例如 return_application；保留原问题中的运费、到账等主题。
        """
        return json.dumps(lookup_faq(query, source), ensure_ascii=False)

    return lookup
