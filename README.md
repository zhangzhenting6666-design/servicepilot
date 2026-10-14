# ServicePilot · 模拟电商售后

Streamlit浅色工作台，真实DeepSeek模型与本地模拟查询工具。
部署入口：ServicePilot/app.py，Python3.13；依赖：根requirements.txt。
服务端Secrets设置DEEPSEEK_API_KEY，切勿写仓库或发聊天。可选DEMO_MAX_CONCURRENT=3、DEMO_MAX_REQUESTS=120。
上限为每次服务进程生命周期的用户轮数，并非token预算；服务重启会重置。云端记录在服务端临时目录，不承诺重启保留。
历史评测4f49d09开发15/15、留出第2轮重测10/10；旧页面7f9f277关键复查5/5。新部署需独立验收。
不执行真实退款/工单，无真实商家接口或真人接入；OpenAI Agents SDK来源及许可见THIRD_PARTY_LICENSE。
