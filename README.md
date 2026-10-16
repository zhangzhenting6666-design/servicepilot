# ServicePilot · 模拟电商售后

在线入口：https://servicepilot-c74sbjqk5s8ppt6tbmwltm.streamlit.app/
四栏工作台：客服体验 / 架构总览 / 项目介绍 / 代码解读。原三栏布局与交互保持；第四栏展示实现原理与源码。
完整代码展示默认收起：按显式22文件清单查看同一稳定快照，带行号、内容摘要与原生复制按钮；不执行代码、不请求模型，无任意路径和源码ZIP下载。
仅产品入口、自有运行模块、模拟数据、CSS、依赖声明、平台配置；排除Secrets/凭证、原始日志、第三方SDK、虚拟环境。
源码快照：ServicePilot/assets/code-guide/snapshot.json；发布commit以Git历史为准。历史证据保留来源版本，不表示当前实时成功。
部署入口：ServicePilot/app.py，Python3.13；依赖：根requirements.txt。
服务端Secrets设置DEEPSEEK_API_KEY，切勿写仓库或发聊天。可选DEMO_MAX_CONCURRENT=3、DEMO_MAX_REQUESTS=120。
上限为每次服务进程生命周期的用户轮数，并非token预算；服务重启会重置。云端记录在服务端临时目录，不承诺重启保留。
历史评测4f49d09开发15/15、留出第2轮重测10/10；旧页面7f9f277关键复查5/5。新部署需独立验收。
不执行真实退款/工单，无真实商家接口或真人接入；OpenAI Agents SDK来源及许可见THIRD_PARTY_LICENSE。
