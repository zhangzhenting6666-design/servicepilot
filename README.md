# ServicePilot · 模拟电商售后

在线体验：[ServicePilot 浅色工作台](https://servicepilot-c74sbjqk5s8ppt6tbmwltm.streamlit.app/)。客服连接真实DeepSeek模型与本地模拟工具，订单及政策为演示数据。

2026-10-15云端必要回归5/5：A1001、缺编号后补充A1002、政策转订单、A9999、新会话隔离。实际页面核对了答复与Agent/查询事件；独立浏览器免登录可用，用户另确认手机移动网络可访问且能查询。390px三个栏目无页面横向溢出，完整SVG和历史图片加载正常。验证代码发布提交7792895；本次README更新不改变应用源码。未将历史25条后台评测或本机回归算作云端结果。

限制：服务可休眠；演示有进程级请求限制，非生产SLA。中文输入法组合态/手机软键盘边界、完整云端25条和云端运行环境日志核对未完成。本机离线39项通过另归属本机候选4bd0f55。

Streamlit浅色工作台，真实DeepSeek模型与本地模拟查询工具。
部署入口：ServicePilot/app.py，Python3.13；依赖：根requirements.txt。
服务端Secrets设置DEEPSEEK_API_KEY，切勿写仓库或发聊天。可选DEMO_MAX_CONCURRENT=3、DEMO_MAX_REQUESTS=120。
上限为每次服务进程生命周期的用户轮数，并非token预算；服务重启会重置。云端记录在服务端临时目录，不承诺重启保留。
历史评测4f49d09开发15/15、留出第2轮重测10/10；旧页面7f9f277关键复查5/5。新部署需独立验收。
不执行真实退款/工单，无真实商家接口或真人接入；OpenAI Agents SDK来源及许可见THIRD_PARTY_LICENSE。
