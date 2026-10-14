"""Native presentation. Dynamic business facts come only from current tool results."""
from html import escape
from base64 import b64encode
from pathlib import Path
import streamlit as st

PRODUCT = Path(__file__).resolve().parents[1]
LABELS = {"ok": "查询成功", "invalid_input": "编号需更正", "not_found": "未找到订单",
          "no_match": "政策未收录", "unavailable": "工具暂不可用"}


def heading(eyebrow, title, description):
    st.markdown(f'<p class="sp-eyebrow">{escape(eyebrow)}</p><h1 class="sp-heading">{escape(title)}</h1>'
                f'<p class="sp-lead">{escape(description)}</p>', unsafe_allow_html=True)


def successful_results(turn):
    if turn.get("status") != "completed":
        return []
    return [e["result"] for e in turn.get("events", []) if e.get("type") == "tool_result"
            and isinstance(e.get("result"), dict) and e["result"].get("status") == "ok"]


def show_facts(turn):
    for result in successful_results(turn):
        order = result.get("order")
        if isinstance(order, dict):
            fields = [("订单号", "order_id"), ("商品", "product"), ("订单状态", "status"),
                      ("承运商", "carrier"), ("模拟运单", "tracking_number")]
            rows = [(label, order[key]) for label, key in fields if order.get(key)]
            st.markdown('<dl class="sp-facts">' + ''.join(
                f'<div><dt>{escape(label)}</dt><dd>{escape(str(value))}</dd></div>'
                for label, value in rows) + '</dl>', unsafe_allow_html=True)
            st.caption("承运商与运单为演示值；没有预计送达时间。" if order.get("tracking_number")
                       else "该模拟订单暂无物流信息。")
        policy = result.get("policy")
        if isinstance(policy, dict):
            with st.container(border=True):
                if policy.get("policy_id"):
                    st.write(policy["policy_id"])
                if policy.get("content"):
                    st.write(policy["content"])


def event_summary(turn):
    if turn.get("status") == "running":
        return "处理中，完成后展示实际事件。"
    if turn.get("status") == "failed":
        return "本次请求失败；以下仅展示已返回的公开事件。"
    results = [e["result"] for e in turn.get("events", []) if e.get("type") == "tool_result"
               and isinstance(e.get("result"), dict)]
    if results:
        return " · ".join(LABELS.get(r.get("status"), "未知结果状态") for r in results)
    return "本次未提供执行事件。" if not turn.get("events") else "本轮公开事件已返回。"


def show_events(turn):
    events = turn.get("events", [])
    if not events:
        st.caption("本次未提供执行事件。" if turn["status"] != "running" else "完成后展示实际事件。")
    for event in events:
        if event.get("type") == "handoff":
            st.write(f"内部转交：{event['source_agent']} → {event['target_agent']}")
        elif event.get("type") == "tool_call":
            st.write(f"调用工具：{event['tool']}")
            st.json(event.get("arguments"), expanded=False)
        elif event.get("type") == "tool_result":
            result = event.get("result", {})
            status = result.get("status") if isinstance(result, dict) else None
            label = LABELS.get(status, "未知结果状态")
            if status == "unavailable":
                st.warning(label)
            elif status in {"not_found", "no_match", "invalid_input"}:
                st.info(label)
            else:
                st.write(label)
            st.json(result, expanded=False)
    if events:
        with st.expander("完整公开事件记录"):
            st.json(events, expanded=False)


def show_architecture():
    heading("架构总览", "从用户提问，到有依据的回答。", "页面管理交互，会话保留上下文，Runner 串联模型与本地工具。")
    path = PRODUCT / "assets/architecture/servicepilot-system-2026-10-14.svg"
    if path.exists():
        svg = path.read_text(encoding="utf-8")
        with st.expander("放大查看完整图"):
            st.caption("仅图形区域可横向滚动。")
            image = b64encode(svg.encode("utf-8")).decode("ascii")
            st.html('<div class="sp-zoom"><img alt="ServicePilot完整架构放大图" '
                    'src="data:image/svg+xml;base64,' + image + '"></div>')
        st.download_button("下载完整 SVG", svg, file_name=path.name, mime="image/svg+xml")
        st.image(svg, width="stretch")
        st.caption("架构资产制作于2026-10-14，图内进度为制作时状态；当前界面已接入，公网验证另记。")
    else:
        st.warning("完整架构图暂不可用。")
    st.markdown("- 模型提出交接与查询请求，Runner 执行本地工具。\n"
                "- 订单与政策来自本地模拟 JSON，不是真实商家接口。\n"
                "- 公开执行事件完成后展示，内部交接不代表接通真人。")


def section(number, label, title):
    st.markdown(f'<div class="sp-section"><span class="sp-section-label">{number} / {escape(label)}</span></div>', unsafe_allow_html=True)
    st.subheader(title)


def show_about():
    with st.container(key="about_content"):
        heading("项目介绍", "让售后助手的行为可检查。", "把“订单到哪了、如何申请退货”拆成可查询、可追问、可核对的流程。基于 OpenAI Agents SDK 与 DeepSeek，在 Codex 协助下完成模拟售后 Demo。")
        left, right = st.columns(2, gap="large")
        with left:
            st.subheader("可体验的能力")
            st.write("订单与政策查询、多轮补充、角色交接、新会话和实际事件查看。")
            st.caption("客服体验栏目连接已有真实模型与本地模拟工具；未预填样例回复。")
        with right:
            st.subheader("验证与边界")
            st.write("固定样本开发15/15、留出第2轮重测10/10；首轮中断记录保留。使用模拟订单与政策，不执行真实退款。")
            st.caption("后台冻结版本4f49d09；不是任意问题准确率或生产效果承诺。")
        section("01", "场景", "从三个具体问题开始。")
        scenarios = [("查询订单", "“我的订单 A1001 到哪了？”", "查询本次模拟记录；没有到货时间就明确说明。"),
                     ("咨询政策", "“签收后几天可以申请退货？”", "查询模拟政策，7天内可提出申请，是否通过需人工审核。"),
                     ("多轮补充", "“帮我查订单。” → “A1002”", "缺编号先追问，补充后在同一会话继续查询。")]
        for column, (label, question, text) in zip(st.columns(3), scenarios):
            with column, st.container(border=True):
                st.caption(label)
                st.write(question)
                st.write(text)
        section("02", "实际运行", "看到回答，也能核对它的来源。")
        st.caption("以下为2026-10-14本机真实历史截图，旧版界面7f9f277（dirty=true，源文件哈希已复核）；不是本次改版或云端验收。")
        images = [("02-a1001-result.jpg", "订单查询：事实来自工具", "A1001 → query_order → 商品、已发货、模拟运单；未补造送达时间。"),
                  ("04-policy-to-order.jpg", "话题切换：同一会话接着处理", "先问政策再查订单，FAQ → Triage → Order，实际调用查询工具。")]
        for column, (filename, title, text) in zip(st.columns(2), images):
            with column:
                path = PRODUCT / "assets/showcase" / filename
                if path.exists():
                    st.image(str(path), caption=title + " · 历史本机截图", width="stretch")
                    with st.expander("查看清晰大图 · " + title):
                        st.image(str(path), width="stretch")
                        st.download_button("下载历史截图", path.read_bytes(), file_name=filename,
                                           mime="image/jpeg", key="image_" + filename)
                else:
                    st.warning("历史截图暂不可用。")
                st.write(text)
        section("03", "工作方式", "模型、执行器、工具，各司其职。")
        steps = [("01 理解与分流", "Triage识别任务；订单与政策专员按职责接手。"),
                 ("02 执行实际动作", "模型提出动作，Runner执行handoff或Python工具。"),
                 ("03 查询业务事实", "工具读取本地JSON，返回本次事实和结果状态。"),
                 ("04 依据结果回答", "模型组织答复，页面展示实际事件，等待下一题。")]
        for column, (title, text) in zip(st.columns(4), steps):
            with column:
                st.write(title)
                st.caption(text)
        st.caption("完整项目图在顶部“架构总览”栏目。")
        section("04", "验证与改进", "用案例检查行为，保留失败与修复。")
        metrics = [("最终开发集", "15 / 15", "后台4f49d09，最终开发轮。"),
                   ("留出第2轮重测", "10 / 10", "后台4f49d09，保留首轮中断。"),
                   ("本机历史关键复查", "5 / 5", "旧页面7f9f277，非新版/云端验收。")]
        for column, (title, value, text) in zip(st.columns(3), metrics):
            with column:
                st.metric(title, value)
                st.caption(text)
        st.caption("固定样本划分公开可见，不是首次外部盲评，不代表总体准确率；本次改版和云端结果另记。")
        with st.expander("只说“转接”并不代表真正交接"):
            st.write("曾出现模型只口头表示转接、没有完成期望动作。调整Triage工具选择配置后，核对真实handoff与最终答复，避免只看文字判断成功。")
        with st.expander("证据保存失败，也需要作为真实失败处理"):
            st.write("留出首轮因Windows文件保存异常中断。保留原记录，增加有界磁盘重试；修复后回归并完整重测，不将重测包装成首次通过。")
        section("05", "项目过程", "从可运行示例，推进到可展示作品。")
        journey = [("10.11", "运行与理解", "接入DeepSeek，运行航空客服基线，理解Agent、工具与交接。"),
                   ("10.13", "售后业务改造", "加入模拟订单、政策工具、多轮补充与边界案例。"),
                   ("10.14", "验证与展示准备", "完成后台评测及本机页面复查，准备架构图、界面与部署。")]
        for column, (date, title, text) in zip(st.columns(3), journey):
            with column:
                st.caption(date)
                st.write(title)
                st.write(text)
        left, right = st.columns(2)
        with left:
            st.subheader("本人参与")
            st.write("需求审阅，模拟规则、功能范围与验收目标确认，本机运行配合和结果审阅。")
        with right:
            st.subheader("实现与协作")
            st.write("Codex协助代码、排错、验证与文档；OpenAI Agents SDK提供执行机制，DeepSeek提供模型服务。")
        st.info("当前工作台已接入现有后台；能否查询取决于服务端配置。公网访问与本次验收以交接记录为准。没有真实退款、工单、真人接入或真实商家接口。")
        st.caption("个人独立实现与掌握程度按实际经历说明。")
