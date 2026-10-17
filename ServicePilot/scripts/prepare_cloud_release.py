"""Export an allowlisted app repository. Does not upload, deploy or include credentials/logs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
import sys
from datetime import datetime, timezone, timedelta

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from servicepilot.source_catalog import PUBLIC_FILES, SNAPSHOT, load_snapshot


def main():
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S")
    output = PRODUCT / "artifacts/deployment" / stamp
    source = output / "source"
    source.mkdir(parents=True, exist_ok=False)
    snapshot = load_snapshot()
    for name in PUBLIC_FILES:
        assert (PRODUCT / name).read_text(encoding="utf-8") == snapshot["files"][name]["text"], "Rebuild public source snapshot"
    paths = [*[PRODUCT / name for name in PUBLIC_FILES if name not in ("requirements.txt", ".streamlit/config.toml")],
             SNAPSHOT,
             PRODUCT / "assets/architecture/servicepilot-system.svg",
             PRODUCT / "assets/showcase/02-a1001-result.jpg", PRODUCT / "assets/showcase/04-policy-to-order.jpg"]
    for path in paths:
        destination = source / "ServicePilot" / path.relative_to(PRODUCT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    shutil.copy2(PRODUCT / "requirements.txt", source / "requirements.txt")
    (source / ".streamlit").mkdir()
    shutil.copy2(PRODUCT / ".streamlit/config.toml", source / ".streamlit/config.toml")
    shutil.copy2(PRODUCT.parent / "openai-agents-python-main/LICENSE", source / "THIRD_PARTY_LICENSE")
    (source / ".gitignore").write_text(".streamlit/secrets.toml\n.env*\n__pycache__/\n*.pyc\n.venv/\nServicePilot/artifacts/\n", encoding="utf-8")
    (source / "README.md").write_text(
        "# ServicePilot · 模拟电商售后\n\n在线入口：https://servicepilot-c74sbjqk5s8ppt6tbmwltm.streamlit.app/\n"
        "四栏工作台：客服体验 / 架构总览 / 项目介绍 / 代码解读。原三栏布局与交互保持；第四栏展示实现原理与源码。\n"
        "完整代码展示默认收起：按显式22文件清单查看同一稳定快照，带行号、内容摘要与原生复制按钮；不执行代码、不请求模型，无任意路径和源码ZIP下载。\n"
        "仅产品入口、自有运行模块、模拟数据、CSS、依赖声明、平台配置；排除Secrets/凭证、原始日志、第三方SDK、虚拟环境。\n"
        "源码快照：ServicePilot/assets/code-guide/snapshot.json；发布commit以Git历史为准。历史证据保留来源版本，不表示当前实时成功。\n"
        "部署入口：ServicePilot/app.py，Python3.13；依赖：根requirements.txt。\n"
        "服务端Secrets设置DEEPSEEK_API_KEY，切勿写仓库或发聊天。可选DEMO_MAX_CONCURRENT=3、DEMO_MAX_REQUESTS=120。\n"
        "上限为每次服务进程生命周期的用户轮数，并非token预算；服务重启会重置。云端记录在服务端临时目录，不承诺重启保留。\n"
        "历史评测4f49d09开发15/15、留出第2轮重测10/10；旧页面7f9f277关键复查5/5。新部署需独立验收。\n"
        "不执行真实退款/工单，无真实商家接口或真人接入；OpenAI Agents SDK来源及许可见THIRD_PARTY_LICENSE。\n", encoding="utf-8")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PRODUCT.parent, text=True).strip()
    manifest = {"created_at": stamp, "kind": "allowlisted_deployment_source_not_deployed",
                "public_snapshot_id": snapshot["snapshot_id"],
                "workspace_commit": revision, "workspace_dirty": bool(subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=PRODUCT.parent, text=True).strip()),
                "entrypoint": "ServicePilot/app.py", "python": "3.13",
                "files": {str(p.relative_to(source)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(source.rglob("*")) if p.is_file()},
                "excluded": ["API credentials", "raw session logs", "personal workspace", "venv", "design prototypes", "Windows lockfile"]}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(output / "servicepilot-cloud-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, str(path.relative_to(source)))
    print(json.dumps({"source": str(source), "archive": str(output / "servicepilot-cloud-source.zip"),
                      "file_count": len(manifest["files"]), "deployed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
