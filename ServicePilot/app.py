"""Light workbench. Replies and events are supplied only by OrderSession."""
from pathlib import Path
import sys
import uuid

PRODUCT = Path(__file__).resolve().parent
sys.path.insert(0, str(PRODUCT))
import streamlit as st
from servicepilot.web_runtime import acceptance_enabled, new_conversation, server_ready, web_version
from servicepilot.workbench_ui import heading, show_about, show_architecture, show_events, show_facts, event_summary
from servicepilot.deployment import bootstrap_from_environment
from servicepilot.code_guide import show_code_guide

st.set_page_config(page_title="ServicePilot · 模拟电商售后", page_icon="💬", layout="wide")
st.set_option("client.toolbarMode", "minimal")
st.html("<style>" + (PRODUCT / "assets/workbench.css").read_text(encoding="utf-8") + "</style>")
st.markdown('<header class="sp-brand"><div class="sp-brand-main"><span class="sp-logo" aria-hidden="true">S</span>'
            '<div><strong>ServicePilot</strong><div class="sp-subtitle">模拟电商售后 · Agent 工作流</div></div>'
            '</div><span class="sp-badge">模拟业务 Demo</span></header>', unsafe_allow_html=True)
bootstrap_from_environment()
c = st.session_state.get("conversation")
if c is None and server_ready():
    try:
        c = new_conversation()
        c.version = web_version()
        c.report["version"] = c.version
        c._save()
        st.session_state.conversation = c
    except Exception:
        st.session_state.initialization_failed = True


def submit(owner):
    st.session_state.notice = c.submit(st.session_state.get("chat_" + owner, ""), uuid.uuid4().hex, owner)


def fill_example(text):
    if not c.busy:
        st.session_state["chat_" + c.session_id] = text


def reset():
    notice = c.reset(bool(st.session_state.get("inject_fault", False)))
    st.session_state.notice = notice or "已开始新会话"
    st.session_state.confirm_reset = False


chat_tab, architecture_tab, about_tab, code_tab = st.tabs(["客服体验", "架构总览", "项目介绍", "代码解读"], key="workbench_nav")
with chat_tab:
    with st.container(key="chat_intro"):
        title, new = st.columns([5, 1], vertical_alignment="center")
        with title:
            heading("客服体验", "让订单与规则查询有依据。", "查询演示订单，或了解模拟退货申请规则。")
        with new:
            if st.button("新会话", disabled=c is None or c.busy, width="stretch"):
                if c.turns:
                    st.session_state.confirm_reset = True
                else:
                    reset()
                    st.rerun()
    st.info("仅使用演示订单与模拟政策。退货申请需人工审核，本 Demo 不直接执行退款。")
    if c is None:
        st.warning("客服暂不可用：服务端尚未配置或初始化失败。架构总览和项目介绍仍可浏览。")
        st.caption("本机请运行“启动聊天页面.cmd”，仅在启动终端输入密钥；云端由项目方配置服务端Secrets。")
        with st.container():
            st.chat_input("客服暂不可用", disabled=True)
    else:
        if acceptance_enabled():
            with st.expander("本机验收控制（只影响新建的测试会话）"):
                st.checkbox("下一新会话注入订单工具故障（C08）", key="inject_fault", disabled=c.busy)
        if c.report.get("fault_injection"):
            st.warning("当前为工具故障测试会话，正常模拟数据未改变。")
        if st.session_state.get("confirm_reset"):
            st.warning("开始新会话后，当前聊天将从页面清除，后台上下文也会重建；已有运行记录仍保留。")
            yes, no = st.columns(2)
            if yes.button("开始新会话", disabled=c.busy):
                reset()
                st.rerun()
            if no.button("取消", disabled=c.busy):
                st.session_state.confirm_reset = False
                st.rerun()
        if st.session_state.get("notice"):
            st.info(st.session_state.notice)
        with st.container(key="workspace"):
            chat, execution = st.columns([2.7, 1], gap="large")
            with chat, st.container(border=True, key="chat_card"):
                if not c.turns:
                    st.markdown('<div class="sp-empty"><h3>今天想了解什么？</h3><p>从一次演示订单或政策查询开始。</p></div>', unsafe_allow_html=True)
                for turn in c.turns:
                    with st.chat_message("user"):
                        st.write(turn["input"])
                    with st.chat_message("assistant"):
                        if turn["status"] == "running":
                            st.write("正在处理，完成后展示答复和实际事件…")
                        elif turn["status"] == "completed":
                            st.markdown(turn["final_answer"])
                            show_facts(turn)
                        else:
                            messages = {"EmptyResponse": "未收到可展示的回复，请重试。",
                                        "DemoBusyError": "当前演示繁忙，请稍后再试。",
                                        "DemoQuotaError": "本次服务演示额度已用完，请联系项目方。"}
                            st.error(messages.get(turn.get("error_type"), "本次未能取得回复，请稍后重试。"))
                            st.caption(f"请求 {turn['request_id'][:8]} · {turn.get('error_type', 'RequestError')}")
                            if st.button("重试此问题", key="retry_" + turn["request_id"], disabled=c.busy):
                                st.session_state.notice = c.submit(turn["input"], uuid.uuid4().hex, c.session_id, retry=True)
                                st.rerun()
                with st.container(horizontal=True):
                    st.button("查一下 A1001", disabled=c.busy, on_click=fill_example, args=("我的订单 A1001 到哪了？",))
                    st.button("了解退货规则", disabled=c.busy, on_click=fill_example, args=("签收后几天内可以申请退货？",))
                st.caption("点击示例只填入，发送后执行查询。")
                st.chat_input("输入订单或售后问题…", key="chat_" + c.session_id, disabled=c.busy,
                              max_chars=2000, on_submit=submit, args=(c.session_id,))
                st.caption("模拟订单与政策 · 不直接执行退款 · Enter发送，Shift+Enter换行")
                st.caption("没有签收日期、预计送达时间、运费或退款到账记录。")
            with execution, st.container(border=True, key="execution_card"):
                st.subheader("执行记录")
                st.caption("来自实际后台记录；内部 Agent 转交不代表接入人工客服。")
                if not c.turns:
                    st.write("发送问题后，这里显示实际执行记录。")
                else:
                    st.write(event_summary(c.turns[-1]))
                    for index, turn in reversed(list(enumerate(c.turns, 1))):
                        with st.expander(f"第 {index} 轮 · {turn['input'][:22]}", expanded=False):
                            show_events(turn)
                            st.caption(f"请求 {turn['request_id'][:8]} · {turn['status']}")
                st.caption("非流式：处理完成后展示实际事件。")
        st.caption(f"会话 {c.session_id[:8]} · 处理中暂停输入和新会话，完成后可继续。")
with architecture_tab:
    show_architecture()
with about_tab:
    show_about()
with code_tab:
    show_code_guide()
st.markdown('<footer class="sp-footer">ServicePilot · 模拟电商售后 · 真实执行与历史验证分开记录</footer>', unsafe_allow_html=True)
if c is not None:
    @st.fragment(run_every=0.5 if c.busy else None)
    def wait_for_result():
        if c.collect():
            st.rerun()
        if c.busy:
            with st.spinner("正在处理，完成后展示答复和实际事件…"):
                st.caption("无需重复发送。")
    wait_for_result()
