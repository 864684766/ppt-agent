# API 目录

API 层负责 HTTP 接入、传输及运行资源的组装；资料规则和模型数据契约仍分别位于 domain、workflows 和 models。

| 目录或文件 | 职责 |
| --- | --- |
| `api_router.py` | 汇总健康检查及业务路由，统一设置业务版本前缀。 |
| `routes/` | 声明 HTTP 路径和 FastAPI 路由入口。 |
| `chat/` | 聊天请求解析、附件和模板处理、资料工作流运行资源、SSE 事件编排及响应组装。 |
| `templates/` | 模板资源接口的存储客户端和目录组装。 |
| `transport/` | HTTP 请求日志中间件和通用 SSE 编码。 |

`main.py` 负责应用生命周期并持有运行资源。SSE 接口为 `/ppt-agent/v1/chat/stream`。续轮请求携带 `previous_task_id`，从当前进程的资料检查点读取已提炼要点，生成本轮结果。[接口调试说明](../docs/调试/接口调试说明.md)
