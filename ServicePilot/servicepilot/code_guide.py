"""Static code guide. Reading, file selection and copy never submit a chat request."""
import streamlit as st

from .source_catalog import PUBLIC_FILES, excerpt, load_snapshot, source_file
from .workbench_ui import heading

LESSONS = (
    {"title": "01 / Agent 分工", "question": "为什么订单问题交给 Order，政策问题交给 FAQ？",
     "conclusion": "角色定义职责和可用工具，模型选择交接，SDK 的 Runner 执行动作。",
     "parts": [("servicepilot/agent_config.py", "    triage.handoffs =", "    return triage, order, faq")],
     "explanation": "Triage 可以交给两个专员；专员跨职责时先回 Triage。FAQ 绑定 lookup_faq，Order 绑定 query_order。同一底层模型可以按不同角色工作，Agent 不是另写的一套模型。",
     "tradeoff": "用明确的工具权限和交接关系约束分工；口头说“转接”不能代替真实 handoff。",
     "evidence": "后台4f49d09评测，以及发布7792895的云端政策→订单观察。历史结论，不是本轮实时执行。",
     "source": "后台4f49d09评测报告；artifacts/workbench/cloud/browser-cases.json（证据留在工作区，不公开原始日志）。"},
    {"title": "02 / 模型接入", "question": "谁提供生成能力，哪里决定调用哪个模型？",
     "conclusion": "AsyncOpenAI 是客户端，DeepSeek 提供服务，RunConfig 把模型配置交给 SDK。",
     "parts": [("servicepilot/model_config.py", 'MODEL =', "    return client, config")],
     "explanation": "服务地址指向 DeepSeek，MODEL 是模型名称。key 是服务端传入的变量，页面不展示它的值。配置关闭 tracing 和自动HTTP重试；45秒是请求超时，不是保证45秒成功。",
     "tradeoff": "Web 与 CLI 复用配置；不同角色可以共用模型连接。模型服务故障仍可能导致整轮失败。",
     "evidence": "冻结4f49d09真实评测使用deepseek-flash；先前云端故障记录InternalServerError，错误按类型保留。",
     "source": "后台4f49d09评测报告；云端请求失败观察记录。"},
    {"title": "03 / 工具查询", "question": "模型怎样知道 A1001 的商品和订单状态？",
     "conclusion": "模型提出带参数的调用，工具校验编号，再读取模拟数据返回结构化事实。",
     "parts": [("servicepilot/order_tools.py", "def query_order(", '    return {"status": "ok"'),
               ("data/orders.json", '    "A1001": {', '\n    },')],
     "explanation": "参数是 order_id，不是整句问题。工具去空格、转大写，要求 A 加四位数字；数据源可以替换。A1001 是蓝牙耳机、已发货、模拟物流、MOCK1001；A1002 的物流字段为空。",
     "tradeoff": "ok、invalid_input、not_found、unavailable 含义分开，便于检查最终回答是否对应本次查询。没有签收日期或预计到货时间，不能推算。",
     "evidence": "旧页面7f9f277的A1001与多轮A1002复查；发布7792895的云端必要回归。项目介绍保留历史截图及来源版本。",
     "source": "旧页面7f9f277订单与多轮复核；云端发布7792895交接记录。"},
    {"title": "04 / 多轮会话", "question": "先说“帮我查订单”，再补“A1002”，程序怎样接上？",
     "conclusion": "OrderSession 保存历史和当前 Agent；新会话会创建新的后台上下文。",
     "parts": [("servicepilot/session.py", "            result = await Runner.run(", "            usage = result.context_wrapper.usage"),
               ("servicepilot/web_runtime.py", "    def reset(self, fault=False):\n        with self.lock:", "            return None")],
     "explanation": "每轮把旧消息与新问题一起交给Runner；成功后保存to_input_list和last_agent。重置先调用backend.reset再生成新session_id，不只清空画面。页面各自持有后台，旧响应还要核对归属。",
     "tradeoff": "处理中禁止重置与重复发送，减少并发混写。历史会增加上下文，不代表支持无限记忆；日志保留也不等于重启恢复聊天。",
     "evidence": "旧页面7f9f277重置与多轮复查；云端已查A1001后重置仍追问编号。",
     "source": "旧页面7f9f277会话重置复核；artifacts/workbench/cloud/final-review.json。"},
    {"title": "05 / 异常与验证", "question": "“没查到订单”和“模型请求失败”为什么不能说成一回事？",
     "conclusion": "业务状态由工具返回；运行异常由会话记录安全类型，页面据此显示失败。",
     "parts": [("servicepilot/session.py", "        except Exception as error:", "        return turn"),
               ("servicepilot/workbench_ui.py", "def event_summary(", "    return \"本次未提供执行事件。\"")],
     "explanation": "not_found 是成功完成查询但没有记录；HTTP/API异常可能连查询都未发生。只保存error_type/http_status，不展示原始响应或请求头。failed 不能显示旧成功事实卡。",
     "tradeoff": "记录工具成功还不够，必须核对最终答复、版本和会话。保存异常也是真实失败；修复后的留出重测不能改称首次盲评。",
     "evidence": "后台4f49d09：开发15/15、留出第2轮10/10；首轮HOLD05保存中断、后五条未运行，原记录保留。上述不是本轮或任意输入的成功率。",
     "source": "后台4f49d09评测报告；artifacts/evaluation/holdout-round1-interruption-review.json。"},
)


def language(name):
    return {".py": "python", ".json": "json", ".css": "css", ".toml": "toml"}.get(
        "." + name.rsplit(".", 1)[-1], "text")


def show_code_guide():
    with st.container(key="code_guide"):
        heading("代码解读", "从业务问题，读到实际实现。", "精选片段与完整文件来自同一稳定源码快照；只读展示，不执行源码或请求模型。")
        try:
            snapshot = load_snapshot()
        except (OSError, ValueError, KeyError, StopIteration):
            st.warning("公开源码快照暂不可用，客服流程不受影响。")
            return
        version = snapshot["snapshot_id"]
        st.caption(f"来源版本：{snapshot['release_label']} · 内容摘要 SHA256 {version[:16]} · UTF-8/LF快照原文；无源码删节。")
        for index, lesson in enumerate(LESSONS):
            with st.container(key=f"code_panel_{index}"):
                st.subheader(lesson["title"])
                st.write("业务问题：" + lesson["question"])
                st.markdown("**" + lesson["conclusion"] + "**")
                for name, first, last in lesson["parts"]:
                    part = excerpt(snapshot, name, first, last)
                    st.caption(f"{name} · 原文件 L{part['start']}–L{part['end']} · 快照 {version[:12]}；代码块不另外从1编号。")
                    st.code(part["text"], language=language(name), height=min(340, 42 + 21 * len(part["text"].splitlines())))
                st.write("白话解释：" + lesson["explanation"])
                st.write("设计取舍：" + lesson["tradeoff"])
                st.caption("历史证据：" + lesson["evidence"])
                st.caption("工作区来源索引：" + lesson["source"])
        with st.expander("完整代码展示", expanded=False, key="full_source"):
            st.write(f"清单内 {len(PUBLIC_FILES)} 个产品文件的完整文本；来源版本 {snapshot['release_label']}，内容摘要 SHA256 {version}。不是整个工作区或第三方SDK源码。")
            st.caption("包含入口、自有运行/展示/部署模块、模拟数据、CSS、依赖声明和平台配置。排除Secrets/密钥值、原始日志、个人文档、测试脚本、第三方SDK仓库、虚拟环境与源码快照自身；无任意路径访问、无源码ZIP下载。")
            st.caption("路径按产品目录列出；发布包把requirements.txt和.streamlit/config.toml放在仓库根目录，其余文件在ServicePilot下，文件正文相同。")
            name = st.selectbox("选择公开产品文件", PUBLIC_FILES, key="public_source_file")
            item = source_file(snapshot, name)
            st.caption(f"文件：ServicePilot/{name} · 全部 {item['line_count']} 行 · SHA256 {item['sha256']}")
            st.caption("代码块右上角复制当前文件的完整正文；行号不进入复制文本。Streamlit展示/复制会去除首尾空行，SHA256按快照原文计算。长代码在自身区域滚动。")
            st.code(item["text"], language=language(name), line_numbers=True, height=440)
            st.caption("没有脱敏删节；构建前按明确清单筛选并检查凭证模式。若代码变化须重建快照后再发布。")
        st.caption("来源与许可：参考OpenAI Agents SDK航空客服示例，SDK由安装包提供；原示例MIT许可随发布包THIRD_PARTY_LICENSE保留。Codex协助实现与验证。")
