# 本项目的 LangSmith 配置

当前截图对应按 Agent 组织的 LangSmith Cloud 工作区，先为本机代码创建一个外部 Agent 的追踪记录。

1. 从 All agents 的新建入口选择 Observability / Trace an existing agent；也可在未选 Agent 的 Tracing 列表选择 New agent。具体按钮随 UI 更新可能变化。
2. 建议显示名称使用 AI PPT 工作台，Agent ID 使用 ppt-agent；ID 创建后不可更改。不要用 Build 中的 Builder 创建另一套运行逻辑。
3. 在 Settings → API Keys 创建该工作区可用的密钥，或使用已有且有效的密钥。本地练习可使用 PAT，仅提交追踪时可评估 tracing key。密钥只填写在本机环境，不发送到聊天或提交仓库。
4. 按账号区域的官方设置说明配置 LANGSMITH_ENDPOINT；填写 LANGSMITH_TRACING、LANGSMITH_API_KEY、LANGSMITH_AGENT_ID 和 LANGSMITH_AGENT_ENVIRONMENT。本机环境使用 local。
5. 不同时设置旧的 LANGSMITH_PROJECT、LANGCHAIN_PROJECT、LANGCHAIN_SESSION；Agent ID 必须是页面显示的实际 ID，不是自行猜测的显示名称。

当前程序尚未接入追踪初始化；Settings 读取 .env 不会自动向 SDK 导出这些变量。仅配置文件或请求 /health 不会产生本项目的模型追踪；后续接入后才验证首次 trace。在 LangSmith 选择该 Agent 的 Tracing，并切换到 Local 查看。

官方依据：

- https://docs.langchain.com/langsmith/create-an-agent
- https://docs.langchain.com/langsmith/log-traces-to-agent
- https://docs.langchain.com/langsmith/create-account-api-key
