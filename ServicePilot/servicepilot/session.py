"""One independent conversation and evidence from actual SDK lifecycle callbacks."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from agents import RunConfig, RunHooks, Runner

from .agent_config import build_agents
from .faq_data import FAQSource
from .order_data import OrderSource

SHANGHAI = timezone(timedelta(hours=8))


def now() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


class EventRecorder(RunHooks):
    def __init__(self):
        self.events: list[dict] = []

    def record(self, kind: str, **details) -> None:
        self.events.append({"time": now(), "type": kind, **details})

    async def on_llm_start(self, context, agent, system_prompt, input_items):
        self.record("model_request", agent=agent.name)

    async def on_handoff(self, context, from_agent, to_agent):
        self.record("handoff", source_agent=from_agent.name, target_agent=to_agent.name)

    async def on_tool_start(self, context, agent, tool):
        arguments = getattr(context, "tool_arguments", None)
        try:
            arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
        except ValueError:
            arguments = {"parse_error": True}
        self.record("tool_call", agent=agent.name, tool=tool.name,
                    call_id=getattr(context, "tool_call_id", None), arguments=arguments)

    async def on_tool_end(self, context, agent, tool, result):
        try:
            output = json.loads(result) if isinstance(result, str) else result
        except ValueError:
            output = {"parse_error": True}
        self.record("tool_result", agent=agent.name, tool=tool.name,
                    call_id=getattr(context, "tool_call_id", None), result=output)


class OrderSession:
    def __init__(self, config: RunConfig, source: OrderSource | None = None, faq_source: FAQSource | None = None):
        self.config = config
        self.triage, self.order, self.faq = build_agents(source, faq_source)
        self.current_agent = self.triage
        self.items: list = []
        self.turns: list[dict] = []

    async def ask(self, question: str) -> dict:
        recorder = EventRecorder()
        turn = {"input": question, "started_at": now(), "starting_agent": self.current_agent.name,
                "events": recorder.events, "status": "running"}
        self.turns.append(turn)
        started = time.perf_counter()
        try:
            result = await Runner.run(
                self.current_agent,
                [*self.items, {"role": "user", "content": question}],
                run_config=self.config, hooks=recorder, max_turns=6,
            )
            self.items = result.to_input_list()
            self.current_agent = result.last_agent
            usage = result.context_wrapper.usage
            turn.update(status="completed", final_answer=str(result.final_output),
                        final_agent=result.last_agent.name,
                        usage={"requests": usage.requests, "input_tokens": usage.input_tokens,
                               "output_tokens": usage.output_tokens, "total_tokens": usage.total_tokens})
        except Exception as error:
            # Keep typed error metadata, never provider response text or request headers.
            turn.update(status="failed", error_type=type(error).__name__,
                        http_status=getattr(error, "status_code", None))
        finally:
            turn.update(finished_at=now(), elapsed_seconds=round(time.perf_counter() - started, 3))
        return turn
