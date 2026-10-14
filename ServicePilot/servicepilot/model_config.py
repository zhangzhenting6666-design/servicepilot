"""One provider configuration shared by CLI and Web; no credential persistence."""

from agents import ModelSettings, OpenAIChatCompletionsModel, RunConfig, set_tracing_disabled
from openai import AsyncOpenAI, DefaultAsyncHttpxClient

MODEL = "deepseek-flash"
BASE_URL = "https://api.deepseek.com"


def create_client_config(key: str):
    set_tracing_disabled(True)
    client = AsyncOpenAI(api_key=key, base_url=BASE_URL, max_retries=0, timeout=45.0,
                         http_client=DefaultAsyncHttpxClient(trust_env=False))
    config = RunConfig(
        model=OpenAIChatCompletionsModel(model=MODEL, openai_client=client),
        model_settings=ModelSettings(max_tokens=1024, parallel_tool_calls=False,
                                    extra_body={"thinking": {"type": "disabled"}}),
        tracing_disabled=True, trace_include_sensitive_data=False,
    )
    return client, config
