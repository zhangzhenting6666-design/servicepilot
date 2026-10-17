"""Run the downloaded airline example with explicit DeepSeek settings."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import importlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime

WORKSPACE = Path(__file__).resolve().parents[2]
REPOSITORY = WORKSPACE / "openai-agents-python-main"
REPORT = WORKSPACE / "ServicePilot" / "artifacts" / "deepseek-latest.json"
MODEL = "deepseek-flash"
BASE_URL = "https://api.deepseek.com"
QUESTION = "What is the baggage allowance?"


def save_report(report: dict) -> None:
    """Save diagnostic metadata only; never save credentials or conversation text."""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def redact(text: str, api_key: str) -> str:
    if api_key:
        text = text.replace(api_key, "[密钥已隐藏]")
    return re.sub(r"(?i)\b(?:sk-[A-Za-z0-9_-]+|Bearer\s+[^\s\"']+)", "[密钥已隐藏]", text)


def clipboard_text() -> str:
    """Read text only when the user presses Ctrl+V in the credential prompt."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    user32.CloseClipboard.argtypes = []
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        pointer = kernel32.GlobalLock(handle) if handle else None
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def masked_key_input() -> str:
    if os.name != "nt" or not sys.stdin.isatty():
        return getpass.getpass("DeepSeek API key: ")
    import msvcrt

    print("DeepSeek API key: ", end="", flush=True)
    characters: list[str] = []
    while True:
        char = msvcrt.getwch()
        if char in ("\r", "\n"):
            print()
            return "".join(characters)
        if char == "\x03":
            print()
            raise KeyboardInterrupt
        if char in ("\x00", "\xe0"):
            msvcrt.getwch()  # Ignore function/arrow keys.
        elif char == "\x16":  # Windows getpass does not handle Ctrl+V.
            pasted = clipboard_text().strip()
            characters.extend(pasted)
            print("*" * len(pasted), end="", flush=True)
        elif char == "\b":
            if characters:
                characters.pop()
                print("\b \b", end="", flush=True)
        else:
            characters.append(char)
            print("*", end="", flush=True)


def read_key(force_prompt: bool = False, report: dict | None = None) -> str:
    key = "" if force_prompt else os.environ.get("DEEPSEEK_API_KEY", "").strip()
    while not key or not key.startswith("sk-") or any(not 33 <= ord(char) <= 126 for char in key) or any(char in key for char in ('"', "'")):
        if key:
            print("输入格式不正确，仍在程序内等待密钥；请复制完整密钥后重试。")
        print("请粘贴新密钥（Ctrl+V），然后按回车；只显示星号，不保存密钥。")
        print("如需退出，按 Ctrl+C。不要把密钥输入到 PS C:\\...> 提示后。")
        key = masked_key_input().strip()
    if report is not None:
        report["key_format"] = {
            "character_count": len(key),
            "has_sk_prefix": key.startswith("sk-"),
            "has_non_printable_or_non_ascii": any(not 33 <= ord(char) <= 126 for char in key),
            "has_quote": any(char in key for char in ('\"', "'")),
        }
    if not key or any(not 33 <= ord(char) <= 126 for char in key):
        raise ValueError("密钥为空或包含空格、不可见控制字符/非英文字符，请重新复制完整密钥。")
    return key


def describe_error(error: Exception, api_key: str, report: dict) -> None:
    """Show a short redacted error instead of a long traceback."""
    report["status"] = "failed"
    report["error_type"] = type(error).__name__
    status = getattr(error, "status_code", None)
    if status is not None:
        report["http_status"] = status
    response = getattr(error, "response", None)
    detail = ""
    if response is not None:
        report["response_bytes"] = len(response.content)
        report["content_type"] = response.headers.get("content-type", "")
        report["server"] = response.headers.get("server", "")
        detail = response.text.strip()
        try:
            body = response.json()
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                message = body["error"].get("message")
                if isinstance(message, str):
                    detail = message
        except (ValueError, TypeError):
            pass
        if not detail:
            detail = "服务器返回了空响应体；无法仅凭 HTTP 状态判断原因。"
    else:
        detail = str(error)
    # Do not persist provider error text: it may echo sensitive request content.
    print(f"\n运行未通过：{type(error).__name__}" + (f"，HTTP {status}" if status else ""))
    print("具体原因：" + redact(detail, api_key)[:1200])
    if status == 401:
        print("下一步：重新复制 DeepSeek 平台的 API 密钥，勿使用网页登录密码。")
    elif status == 402:
        print("下一步：检查 DeepSeek API 账户余额。")
    elif status == 400:
        print("下一步：把上面的“具体原因”发给我；不要连续重试。")


async def run(args: argparse.Namespace, api_key: str, report: dict) -> int:
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient

    from agents import (
        HandoffOutputItem,
        ItemHelpers,
        MessageOutputItem,
        ModelSettings,
        OpenAIChatCompletionsModel,
        RunConfig,
        Runner,
        ToolCallItem,
        ToolCallOutputItem,
        set_tracing_disabled,
    )

    set_tracing_disabled(True)
    # Do not retry failed requests automatically or export third-party traces.
    async with AsyncOpenAI(
        api_key=api_key,
        base_url=BASE_URL,
        max_retries=0,
        timeout=45.0,
        http_client=DefaultAsyncHttpxClient(trust_env=False),
    ) as client:
        report["phase"] = "check_api_key_and_model"
        report["network"] = "direct_without_environment_proxy"
        print("1. 检查密钥与模型列表（不生成回答）……", flush=True)
        report["api_request_attempted"] = True
        try:
            models = await client.models.list()
        except Exception:
            # Compare another installed HTTP implementation without generating tokens.
            import requests

            def compare_transport() -> dict:
                with requests.Session() as session:
                    session.trust_env = False
                    response = session.get(
                        BASE_URL + "/models",
                        headers={"Authorization": "Bearer " + api_key},
                        timeout=15,
                        allow_redirects=False,
                    )
                    result = {"http_status": response.status_code, "response_bytes": len(response.content)}
                    # A known-invalid credential distinguishes account-specific from network failures.
                    control = session.get(
                        BASE_URL + "/models",
                        headers={"Authorization": "Bearer diagnostic-placeholder"},
                        timeout=15,
                        allow_redirects=False,
                    )
                    result["invalid_key_control_status"] = control.status_code
                    result["invalid_key_control_response_bytes"] = len(control.content)
                    return result

            try:
                comparison = await asyncio.to_thread(compare_transport)
                report["alternate_http_check"] = comparison
                print(f"   独立网络检查：HTTP {comparison['http_status']}，响应 {comparison['response_bytes']} 字节。")
                print(f"   对照检查（测试凭据）：HTTP {comparison['invalid_key_control_status']}。")
            except Exception as comparison_error:
                report["alternate_http_check"] = {"error_type": type(comparison_error).__name__}
            raise
        available = {item.id for item in models.data}
        report["model_available"] = MODEL in available
        report["api_key_verified"] = True
        if MODEL not in available:
            raise ValueError(f"密钥验证通过，但账户模型列表中没有 {MODEL}。")
        print(f"   通过：密钥有效，{MODEL} 可用。", flush=True)
        if args.check_only:
            report["status"] = "api_check_passed"
            return 0

        # Import the user's downloaded example, not the other vendored copy.
        # The sample reads its key at import time; restore the previous environment afterward.
        old_key = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = api_key
        try:
            sys.path.insert(0, str(REPOSITORY))
            sample = importlib.import_module("examples.customer_service.main")
        finally:
            if old_key is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = old_key

        actual_source = Path(sample.__file__).resolve()
        report["example_file"] = str(actual_source)
        # RunConfig overrides the model and settings for all agents, including handoffs.
        config = RunConfig(
            model=OpenAIChatCompletionsModel(model=MODEL, openai_client=client),
            model_settings=ModelSettings(
                max_tokens=1024,
                parallel_tool_calls=False,
                extra_body={"thinking": {"type": "disabled"}},
            ),
            tracing_disabled=True,
            trace_include_sensitive_data=False,
        )
        for agent in (sample.triage_agent, sample.faq_agent, sample.seat_booking_agent):
            for agent_tool in agent.tools:
                agent_tool.strict_json_schema = False
            for agent_handoff in agent.handoffs:
                agent_handoff.strict_json_schema = False

        current_agent = sample.triage_agent
        context = sample.AirlineAgentContext()
        items: list = []
        report["phase"] = "airline_customer_service"
        report["thinking"] = "disabled"
        report["max_turns_per_question"] = 6
        report["completed_questions"] = 0
        report["model_requests"] = 0
        report["handoffs"] = []
        report["tools_called"] = []
        try:
            if actual_source != REPOSITORY / "examples" / "customer_service" / "main.py":
                raise ValueError("导入了另一份客服示例，请检查项目路径。")
            print("2. 运行官方航空客服流程（会使用少量 DeepSeek 余额）。", flush=True)
            while True:
                question = input("请输入问题（exit 退出）： ") if args.interactive else QUESTION
                if question.strip().lower() in {"exit", "quit", "退出"}:
                    report["status"] = "finished" if report["completed_questions"] else "not_run"
                    return 0
                if not question.strip():
                    continue
                if not args.interactive:
                    print("测试问题：" + question, flush=True)
                items.append({"role": "user", "content": question})
                report["model_generation_attempted"] = True
                result = await Runner.run(
                    current_agent,
                    items,
                    context=context,
                    run_config=config,
                    max_turns=6,
                )
                for item in result.new_items:
                    if isinstance(item, HandoffOutputItem):
                        names = [item.source_agent.name, item.target_agent.name]
                        report["handoffs"].append(names)
                        print(f"客服转交：{names[0]} → {names[1]}")
                    elif isinstance(item, ToolCallItem):
                        name = getattr(item.raw_item, "name", "tool")
                        report["tools_called"].append(name)
                        print(f"{item.agent.name} 调用工具：{name}")
                    elif isinstance(item, ToolCallOutputItem):
                        print(f"{item.agent.name} 已取得工具结果。")
                    elif isinstance(item, MessageOutputItem):
                        print(f"{item.agent.name}：{ItemHelpers.text_message_output(item)}")
                usage = result.context_wrapper.usage
                report["model_requests"] += usage.requests
                report["completed_questions"] += 1
                report["status"] = "passed"
                print(f"本轮完成，共 {usage.requests} 次模型请求。", flush=True)
                save_report(report)
                items = result.to_input_list()
                current_agent = result.last_agent
                if not args.interactive:
                    return 0
        finally:
            await sample.deepseek_client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Only validate API key and model.")
    parser.add_argument("--interactive", action="store_true", help="Ask multiple questions manually.")
    parser.add_argument("--fresh-key", action="store_true", help="Prompt for a fresh key instead of reusing the shell environment.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "not_started",
        "phase": "local_setup",
        "model": MODEL,
        "base_url": BASE_URL,
        "api_request_attempted": False,
        "model_generation_attempted": False,
    }
    api_key = ""
    try:
        api_key = read_key(force_prompt=args.fresh_key, report=report)
        exit_code = asyncio.run(run(args, api_key, report))
        return exit_code
    except (KeyboardInterrupt, EOFError):
        report["status"] = "cancelled"
        print("\n已退出。")
        return 130
    except Exception as error:
        describe_error(error, api_key, report)
        return 1
    finally:
        save_report(report)
        print("诊断记录已保存（不含密钥或对话）：" + str(REPORT))


if __name__ == "__main__":
    raise SystemExit(main())
