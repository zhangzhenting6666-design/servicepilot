# ServicePilot 项目学习与建设路线图：生成规格

用途：面试项目介绍配图；归纳已有真实经历，说明从官方示例到应用的推进路径。使用内置 image_gen 生成，不修改运行网站。

生成提示词：

Use case: infographic-diagram.
Create one polished Chinese infographic flowchart for an interview presentation, landscape 16:10, high resolution, extremely legible accurate Simplified Chinese typography. Elegant restrained editorial/product portfolio visual. Warm-white background, white rounded cards, thin pale gray-green borders, forest-green titles and arrows, very subtle shadows. Match ServicePilot's established light green palette. No dates, calendar timestamps, mock UI screenshots, decorative gradients, self-test questions, personal mastery disclaimers, or claims of independent SDK development. Do not invent capabilities or experience. This is a project development and learning roadmap, not the runtime system architecture diagram.

Main title, exact: “ServicePilot｜从官方示例到可展示作品”
Subtitle, exact: “复现与理解 → 业务改造与验证 → 产品化与迭代”

Composition: three clearly labeled horizontal stages stacked vertically, each containing three generous numbered cards. All cards in each stage read left to right with explicit arrows. Connect the stages with a subtle vertical progression line at the far left, without crossing card text. Number the nine cards 01–09 in reading order. Stage 1 contains cards 01–03, stage 2 contains cards 04–06, stage 3 contains cards 07–09. Include minimal relevant line icons (repository, environment, magnifier, target, code, checklist, chat, cloud, refinement). Prioritize text accuracy and hierarchy over decorative elements. Card body must not be too small. Generous spacing, clean margins. No extra cards, numbers, labels, claims, or logos.

Stage 1 exact label: “第一阶段｜复现与理解”
Card 01 title: “获取官方示例”
Card 01 body lines:
“从 GitHub 下载官方代码”
“以航空客服示例作为学习起点”

Card 02 title: “搭建运行环境”
Card 02 body lines:
“配置 Python、虚拟环境与依赖”
“接入 DeepSeek，安全配置密钥”

Card 03 title: “跑通并追踪流程”
Card 03 body lines:
“沿「行李额度」问答阅读代码”
“理解输入、分流、工具与回答”

Stage 2 exact label: “第二阶段｜业务改造与验证”
Card 04 title: “明确产品目标”
Card 04 body lines:
“从航空客服转向模拟电商售后”
“确认 PRD、业务范围与验收目标”

Card 05 title: “按职责改造代码”
Card 05 body lines:
“Triage / Order / FAQ 分工”
“参数化工具、JSON 数据与多轮会话”

Card 06 title: “真实验证与排错”
Card 06 body lines:
“先开发集，再冻结版本评测留出集”
“保留路由、参数、答复与失败记录”

Stage 3 exact label: “第三阶段｜产品化与迭代”
Card 07 title: “搭建聊天界面”
Card 07 body lines:
“使用 Streamlit 构建中文页面”
“聊天、新会话、状态提示与实际事件”

Card 08 title: “发布并核对效果”
Card 08 body lines:
“GitHub 管理版本，Streamlit 部署”
“分别记录本机验证、上传与线上确认”

Card 09 title: “根据反馈持续精修”
Card 09 body lines:
“四栏展示、源码快照与手机适配”
“修复展示缓存，优化面板层次”

Below the three stages, an elegant compact full-width strip:
Exact label: “我的推进重点”
Exact content: “需求与范围把控 · 验收目标确认 · 运行结果审阅 · 界面反馈与迭代”

Small but readable footer, exact: “技术基础：OpenAI Agents SDK · DeepSeek · Python · Streamlit   ｜   Codex 协作开发”

No fabricated success metrics, mastery claims, real merchant integration, real refunds, tickets, login, or production-scale capability. Do not add a disclaimer about the person not mastering code. Keep the diagram affirmative, professional, honest and suitable for an interviewer. Spell technical names precisely. All requested text must be included once, with no extra explanatory paragraphs.
