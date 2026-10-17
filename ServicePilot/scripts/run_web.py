"""Start localhost Streamlit after one masked terminal credential input."""
import argparse
import os
from pathlib import Path
import sys

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from run_deepseek_customer_service import read_key
from servicepilot.web_runtime import configure_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--acceptance-controls", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    print("ServicePilot 本地页面：请仅在下方提示中输入密钥，不输入聊天或浏览器。", flush=True)
    key = read_key(force_prompt=True)
    configure_server(key, args.acceptance_controls, args.port)
    os.chdir(PRODUCT)
    print(f"打开 http://127.0.0.1:{args.port} ；此窗口保持运行，Ctrl+C 停止。", flush=True)
    from streamlit.web import cli
    cli.main(args=["run", str(PRODUCT / "app.py"), "--server.address=127.0.0.1",
                   f"--server.port={args.port}", "--server.headless=true",
                   "--browser.gatherUsageStats=false", "--server.fileWatcherType=none",
                   "--client.showErrorDetails=false"], standalone_mode=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("本地页面已停止。")
    except Exception as error:
        print(f"页面启动失败：{type(error).__name__}。未输出原始异常，避免泄露凭据。")
        raise SystemExit(1)
