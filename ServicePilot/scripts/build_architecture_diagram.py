"""Build a dated, editable architecture asset; does not import or run the app."""

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "architecture"
OUT.mkdir(parents=True, exist_ok=True)
STEM = "servicepilot-system-2026-10-14"
W, H = 1680, 2110
C = dict(ink="#173347", muted="#5b7180", teal="#147e70", blue="#346fce",
         purple="#8868b4", amber="#9a641c", border="#d6e2df", bg="#f8faf8")
parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">ServicePilot 模拟电商售后系统完整运行架构</title>
<desc id="desc">用户界面、会话、SDK Runner和三种Agent、本地工具、模拟JSON、答复返回；右侧为模型服务、运行配置、实际事件和业务边界。当前本机已实现，公网部署与新栏目待实现。</desc>
<defs>
 <filter id="shadow" x="-10%" y="-15%" width="120%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="6" flood-color="#1b3d31" flood-opacity="0.035"/></filter>
 <marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M1,1 L8.5,5 L1,9" fill="none" stroke="{C['teal']}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></marker>
 <marker id="sidearrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1,1 L8.5,5 L1,9" fill="none" stroke="#7c93a0" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></marker>
</defs>
<style>text {{font-family:'Microsoft YaHei','Noto Sans CJK SC','Segoe UI',sans-serif; fill:{C['ink']};}} .muted{{fill:{C['muted']};}} .small{{font-size:22px;}} .body{{font-size:25px;}} .head{{font-size:32px;font-weight:700;}} .mono{{font-family:'Cascadia Code',Consolas,'Microsoft YaHei',monospace;}}</style>
<rect width="1680" height="2110" fill="{C['bg']}"/>
''']


def rect(x, y, w, h, fill="white", stroke=None, radius=22, dash=False, shadow=True):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke or C["border"]}" stroke-width="2"'
                 + (' stroke-dasharray="9 7"' if dash else '')
                 + (' filter="url(#shadow)"' if shadow else '') + '/>')


def text(x, y, content, size=25, color=None, weight=400, anchor="start", mono=False):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}"'
                 + (f' style="fill:{color}"' if color else '')
                 + (' class="mono"' if mono else '') + f'>{escape(content)}</text>')


def lines(x, y, content, size=25, gap=37, color=None, weight=400, anchor="start"):
    for n, line in enumerate(content):
        text(x, y+n*gap, line, size, color, weight, anchor)


def path(d, side=False, both=False, dashed=False, width=3):
    marker = "sidearrow" if side else "arrow"
    parts.append(f'<path d="{d}" fill="none" stroke="{("#7c93a0" if side else C["teal"])}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round" marker-end="url(#{marker})"'
                 + (f' marker-start="url(#{marker})"' if both else '')
                 + (' stroke-dasharray="7 7"' if dashed else '') + '/>')


def label(x, y, w, title, color, fill):
    rect(x, y-28, w, 40, fill, fill, radius=20, shadow=False)
    text(x+w/2, y, title, 21, color, 600, "middle")


def step(x, y, number, title, desc, color=C["blue"], fill="#f0f5ff", h=130):
    rect(x, y, 984, h, fill, color)
    rect(x+24, y+25, 52, 52, color, color, radius=15, shadow=False)
    text(x+50, y+61, number, 28, "white", 700, "middle")
    text(x+96, y+53, title, 33, C["ink"], 700)
    lines(x+96, y+93, desc, 25, 34, C["muted"])


# Header: short promise first, status on a separate line.
text(64, 85, "ServicePilot｜完整运行架构", 49, weight=750)
text(66, 132, "从用户提问，到有依据的回答：界面 → 会话 → Agent → 工具与数据 → 页面", 26, C["muted"])
label(66, 180, 182, "本机已实现", C["teal"], "#e1f1ea")
text(270, 180, "模拟电商售后 Demo · 逻辑职责分层 · 2026.10.14", 23, C["muted"])

# Main spine. Return path sits in the left gutter and never passes through cards.
step(144, 222, "01", "Streamlit 聊天页面", ["用户提问 / 客服答复 / 新会话 / 实际执行事件"], C["purple"], "#f4f0fa")
path("M636 352 V400")
step(144, 400, "02", "Python 应用与会话", ["历史消息 + 当前 Agent + 会话 / 请求标识", "缺信息先追问；同会话补充接续；新会话重建上下文"], h=148)
path("M636 548 V594")

# SDK is a container around the roles, rather than a fourth agent.
rect(112, 594, 1048, 520, "white", "#98bcb2")
text(148, 643, "03  OpenAI Agents SDK / Runner", 34, C["teal"], 700)
text(148, 683, "请求模型 → 执行交接或工具 → 按需继续 → 返回本轮结果", 25, C["muted"])
rect(390, 723, 468, 120, "#eef4ff", "#6a96e2")
text(624, 770, "Triage Agent", 34, weight=700, anchor="middle")
text(624, 810, "识别请求，交给对应专员", 25, C["muted"], anchor="middle")
path("M490 843 V892 H343 V936", both=True)
path("M758 843 V892 H913 V936", both=True)
text(278, 880, "政策问题", 23, C["teal"], anchor="middle")
text(978, 880, "订单问题", 23, C["teal"], anchor="middle")
rect(144, 936, 398, 125, "#eaf5ef", "#67a594")
text(343, 982, "FAQ Agent", 33, weight=700, anchor="middle")
text(343, 1024, "查询退货规则与政策", 25, C["muted"], anchor="middle")
rect(714, 936, 398, 125, "#eaf5ef", "#67a594")
text(913, 982, "Order Agent", 33, weight=700, anchor="middle")
text(913, 1024, "追问编号，查询订单与物流", 24, C["muted"], anchor="middle")
text(636, 1094, "专员切换：先返回 Triage，再交给另一位专员", 23, C["teal"], anchor="middle")

# Function calls: business roles request, the Runner executes.
path("M343 1061 V1162")
path("M913 1061 V1162")
rect(144, 1162, 398, 125, "#f2f6f4", "#9ab2a9")
text(343, 1197, "04  Python 查询工具", 22, C["muted"], anchor="middle")
text(343, 1236, "lookup_faq(query)", 27, weight=650, anchor="middle", mono=True)
text(343, 1269, "查询政策，返回状态与依据", 23, C["muted"], anchor="middle")
rect(714, 1162, 398, 125, "#f2f6f4", "#9ab2a9")
text(913, 1197, "04  Python 查询工具", 22, C["muted"], anchor="middle")
text(913, 1236, "query_order(order_id)", 26, weight=650, anchor="middle", mono=True)
text(913, 1269, "规范编号，查询当前模拟记录", 23, C["muted"], anchor="middle")
text(628, 1208, "Runner", 20, C["muted"], anchor="middle")
text(628, 1240, "执行工具", 20, C["muted"], anchor="middle")
path("M343 1287 V1342", both=True)
path("M913 1287 V1342", both=True)
rect(144, 1342, 398, 127, "#f2f6f4", "#9ab2a9")
text(343, 1375, "05  本地模拟政策", 24, C["teal"], 650, "middle")
text(343, 1412, "policies.json", 26, weight=650, anchor="middle", mono=True)
text(343, 1446, "RET-001 · 退货申请规则", 23, C["muted"], anchor="middle")
rect(714, 1342, 398, 127, "#f2f6f4", "#9ab2a9")
text(913, 1375, "05  本地模拟订单", 24, C["teal"], 650, "middle")
text(913, 1412, "orders.json", 26, weight=650, anchor="middle", mono=True)
text(913, 1446, "A1001 / A1002 / A1003", 23, C["muted"], anchor="middle")

path("M343 1469 V1514 H636 V1576")
path("M913 1469 V1514 H636")
rect(414, 1497, 444, 35, C["bg"], C["bg"], radius=8, shadow=False)
text(636, 1522, "查询结果回传 Runner → 再请求模型", 22, C["teal"], anchor="middle")
step(144, 1576, "06", "答复与实际事件返回页面", ["模型依据工具结果回答；保存历史与当前 Agent", "本轮结束后等待用户下一条输入"], h=148)
path("M144 1650 H80 V287 H144", width=3.5)
parts.append(f'<text x="44" y="1190" font-size="23" font-weight="600" style="fill:{C["teal"]}" transform="rotate(-90 44 1190)">回到界面，继续下一轮对话</text>')

# Sidebar: support relationships outside the execution spine.
rect(1224, 222, 392, 300, "#f0f4f2", "#b6c8c0")
text(1252, 271, "运行与配置", 31, weight=700)
lines(1252, 321, ["Python + 项目 venv", "依赖与版本记录", "服务地址与模型名", "API 密钥仅在服务端", "当前由终端隐藏输入"], 24, 37, C["muted"])
path("M1224 465 H1128", side=True, dashed=True)
rect(1224, 594, 392, 255, "#eef4ff", "#87a8df")
text(1252, 644, "DeepSeek API", 32, weight=700)
text(1252, 684, "远端模型：deepseek-flash", 23, C["blue"])
lines(1252, 728, ["理解问题，选择交接或工具", "根据工具结果组织答复", "三个角色共用同一模型配置"], 24, 37, C["muted"])
path("M1160 746 H1224", side=True, both=True, dashed=True)
text(1192, 726, "API", 18, C["muted"], anchor="middle")
rect(1224, 906, 392, 255, "#f0f4f2", "#b6c8c0")
text(1252, 956, "实际事件与证据", 31, weight=700)
lines(1252, 1006, ["内部交接、工具参数与结果", "会话 / 请求、版本与耗时", "记录实际模型请求和 usage", "页面可展开，便于核对来源"], 24, 37, C["muted"])
path("M1160 1031 H1224", side=True, dashed=True)
rect(1224, 1218, 392, 251, "#fff7e9", "#d4b078")
text(1252, 1268, "业务边界", 31, C["amber"], 700)
lines(1252, 1317, ["只读模拟订单与政策", "退货申请需人工审核", "无退款执行 / 真人接入", "无签收日期 / 预计送达"], 24, 37, C["amber"])
rect(1224, 1530, 392, 194, "#f7f3fa", "#a68cc4", dash=True)
text(1252, 1577, "后续规划 · 未实现", 29, C["purple"], 700)
lines(1252, 1622, ["公网部署 / 架构展示栏目", "模拟工单（后续可选）"], 24, 39, C["muted"])

# Validation is a support strip, never another business role.
rect(64, 1790, 1552, 231, "white", "#c5d8cf")
text(98, 1840, "验证与持续改进", 32, C["teal"], 700)
text(98, 1883, "已实现：订单与政策查询 · 多轮补充 · 内部交接 · 新会话与页面隔离 · 实际事件", 25, C["muted"])
label(98, 1941, 260, "开发集 15/15", C["teal"], "#e8f3ed")
label(390, 1941, 300, "留出重测 10/10", C["teal"], "#e8f3ed")
label(722, 1941, 402, "最新本机页面关键复查 5/5", C["blue"], "#edf3fc")
text(98, 1992, "固定样本；首轮中断与修复记录保留。不同证据对应各自被测版本，不代表云端已验收。", 22, C["muted"])
text(66, 2070, "实线：主要处理与交接 / 返回    虚线：模型请求与支撑关系    紫色虚线卡片：后续规划", 22, C["muted"])

parts.append("</svg>")
(OUT / f"{STEM}.svg").write_text("\n".join(parts), encoding="utf-8")
html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ServicePilot · 架构总览</title>
<style>body{{margin:0;background:#f2f5f2;color:#173347;font:16px/1.7 'Microsoft YaHei',sans-serif}}header{{max-width:1150px;margin:25px auto;padding:0 20px}}a{{color:#147e70;margin-right:22px}}figure{{margin:0 auto 40px;max-width:1280px}}figure img{{width:100%;height:auto;display:block}}.tip{{color:#5b7180;font-size:14px}}button{{background:#147e70;color:white;border:0;border-radius:8px;padding:8px 15px;cursor:pointer}}body.zoom figure{{max-width:none;width:1680px}}@media print{{header{{display:none}}figure{{max-width:100%}}}}</style>
<header><strong>ServicePilot · 架构总览</strong><p><a href="{STEM}.png" download>下载高清 PNG</a><a href="{STEM}.svg" download>下载可编辑 SVG</a><a href="../../docs/2026-10-14-ServicePilot完整架构说明.md">文字说明</a><button onclick="document.body.classList.toggle('zoom')">切换原尺寸 / 自适应</button></p><p class="tip">当前本机实现 · 2026-10-14。页面中的“架构总览”栏目仍待接入；此文件是独立图片预览。</p></header><figure><img src="{STEM}.svg" alt="ServicePilot 完整运行架构，详细文字见架构说明"></figure></html>'''
(OUT / f"{STEM}.html").write_text(html, encoding="utf-8")
print(f"Built {OUT / (STEM + '.svg')}")
