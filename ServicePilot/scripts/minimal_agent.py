"""Run one real Agent turn; a missing key is a blocker, never a simulated success."""
import asyncio
import time

from agents import Agent, Runner
from agents.models.default_models import get_default_model

from day1_support import configure_client, failure, metadata, save

PROMPT = "Reply with exactly: ServicePilot Day 1 OK"


async def main() -> int:
    model = get_default_model()
    record = metadata("minimal-agent", model, PROMPT)
    if not record["credential_present"]:
        record.update(status="blocked_missing_credentials", api_request_attempted=False,
                      reason="OPENAI_API_KEY is absent. No model API request was made.")
        save(record)
        return 2
    started = time.perf_counter()
    try:
        configure_client()
        agent = Agent(name="ServicePilot Day 1 Probe", instructions="Follow the user instruction exactly.", model=model)
        record["api_request_attempted"] = True
        result = await asyncio.wait_for(Runner.run(agent, PROMPT, max_turns=2), timeout=90)
        usage = result.context_wrapper.usage
        record.update(status="succeeded", real_call_succeeded=True,
                      final_agent=result.last_agent.name,
                      output_check_passed=result.final_output.strip() == "ServicePilot Day 1 OK",
                      usage={k: getattr(usage, k) for k in ("requests", "input_tokens", "output_tokens", "total_tokens")})
        output = result.final_output
    except Exception as exc:
        failure(record, exc)
        output = ""
    record["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    save(record, output)
    return 0 if record["real_call_succeeded"] and record["output_check_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
