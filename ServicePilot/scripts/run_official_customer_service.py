"""Execute the unchanged official main() with one bounded FAQ input and local evidence."""
import asyncio
import contextlib
import importlib
import io
import sys
import time

from agents.models.default_models import get_default_model

from day1_support import ROOT, configure_client, failure, metadata, save

PROMPT = "What is the baggage allowance? Please use your FAQ lookup tool."


async def main() -> int:
    sys.path.insert(0, str(ROOT / "vendor" / "openai-agents-python"))
    official = importlib.import_module("examples.customer_service.main")
    record = metadata("official-customer-service", get_default_model(), PROMPT)
    record["source_commit"] = "125efa029b4bfd84238bd2c4fd69c3406f802663"
    record["official_module_imported"] = True
    record["harness_changes"] = "Fixed FAQ input; one-turn auto mode; tracing export disabled; unchanged official main() and agents/tools."
    if not record["credential_present"]:
        record.update(status="blocked_missing_credentials", api_request_attempted=False,
                      reason="Official module imported; OPENAI_API_KEY is absent. Official model call was not started.")
        save(record)
        return 2
    output = io.StringIO()
    started = time.perf_counter()
    try:
        configure_client()
        # Only adapt console input and exit behavior. Keep upstream file bytes unchanged.
        def fixed_input(prompt: str, fallback: str) -> str:
            print(f"[day1-input] {PROMPT}")
            return PROMPT
        official.input_with_fallback = fixed_input
        official.is_auto_mode = lambda: True
        record["api_request_attempted"] = True
        with contextlib.redirect_stdout(output):
            await asyncio.wait_for(official.main(), timeout=90)
        text = output.getvalue()
        record.update(status="succeeded", real_call_succeeded=True,
                      faq_handoff_observed="Handed off from Triage Agent to FAQ Agent" in text,
                      faq_tool_output_observed="FAQ Agent: Tool call output:" in text)
        record["day1_acceptance_passed"] = record["faq_handoff_observed"] and record["faq_tool_output_observed"]
    except Exception as exc:
        failure(record, exc)
    record["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    save(record, output.getvalue())
    return 0 if record["real_call_succeeded"] and record["faq_handoff_observed"] and record["faq_tool_output_observed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
