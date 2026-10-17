# DeepSeek 航空客服运行说明

航空示例已完成真实运行，B-01 流程学习也已完成。2026-10-13 C-00 已保存航空基线，C-01 首条订单查询及 C02 已实测通过；电商启动方式见[基线与启动说明](基线与启动说明.md)。本文保留航空运行方法。航空入口复用 `openai-agents-python-main/examples/customer_service/main.py` 的客服角色、交接与工具，通过 SDK 的 `RunConfig` 统一指定 DeepSeek。

## 怎么运行

双击 `ServicePilot/启动航空客服.cmd`。如果当前进程没有密钥，窗口会要求在本机粘贴 DeepSeek API 密钥；输入不显示，密钥不写入文件。随后先查询模型列表验证密钥，再自动问一次 `What is the baggage allowance?`。一次问题可能产生多次模型请求，分别用于转交客服、查询工具和组织答案。

也可以在下载仓库根目录 `openai-agents-python-main` 的 PowerShell 执行（不是 vibe coding 或 ServicePilot 根目录）：

```powershell
.\.venv\Scripts\python.exe -X utf8 ..\ServicePilot\scripts\run_deepseek_customer_service.py
```

只验证密钥和模型列表、不生成回答：在上面的命令末尾加 `--check-only`。连续对话：加 `--interactive`，输入 `exit` 退出。

重新输入新密钥：加 `--check-only --fresh-key`，等出现 `DeepSeek API key:` 后再按 Ctrl+V 粘贴并回车。Windows 输入入口已支持 Ctrl+V，只显示星号；空输入或格式错误会继续等待，不会直接回到 PowerShell。按 Ctrl+C 可退出。`PS C:\...>` 表示 PowerShell 正在等待命令，此时不要粘贴密钥。

2026-10-11 的诊断记录显示一次输入只有一个不可见控制字符，尚未发出 API 请求。修复输入后，有效密钥下模型检查与航空问答已通过。早期空白 HTTP 400 与控制字符输入之间未单独验证因果关系，不把输入问题写成已证明的唯一根因。截图中已经暴露的旧密钥应在 DeepSeek 控制台撤销；是否撤销由用户在平台确认。

## 为什么这样配置

- 使用 DeepSeek 官方标准接口 `https://api.deepseek.com` 与 `deepseek-flash`。
- 明确关闭思考模式，先运行简单客服流程，避免依赖思考内容回传的额外兼容要求。DeepSeek 当前默认开启思考模式，带工具的后续请求必须完整回传思考内容；见[官方说明](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)。这只是针对兼容性的简化配置，尚未确认是之前 400 的根因。
- 关闭工具严格模式与并行工具调用；每次模型输出最多 1024 tokens，每个问题最多 6 轮。失败时不自动重复 SDK 请求。
- 关闭 OpenAI tracing。诊断文件 `ServicePilot/artifacts/deepseek-latest.json` 只记录运行阶段、状态、调用次数及错误元数据，不保存密钥、问题、回答或工具参数。错误的具体描述只在本机窗口显示。

## 当前验证范围

早期本地模拟检查验证了交接、工具执行、错误提示与脱敏，这些模拟检查没有生成付费模型回答。随后用户本机输入有效密钥，在 deepseek-flash 下完成 3 个航空问题、合计 12 次模型请求，真实证据见 `artifacts/airline-baseline-2026-10-11.json`。选座只验证意图与追问，没有完成座位更新；Wi-Fi 答复未达到预期，源码有 Wi-Fi 规则但实际工具参数未保存，具体原因仍待复现。电商功能与案例均未验证。
