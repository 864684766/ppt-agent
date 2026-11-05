"""每条执行链独立的日志编号；异步并发请求不会共享同一个可变编号。"""

import logging
from contextvars import ContextVar


# ContextVar按执行上下文隔离；asyncio.to_thread会复制当前上下文。
# '-'表示当前没有HTTP请求或正在执行的操作，不是业务项目ID/会话ID。
request_id: ContextVar[str] = ContextVar("log_request_id", default="-")
operation_id: ContextVar[str] = ContextVar("log_operation_id", default="-")


class LogContextFilter(logging.Filter):
    """为本项目处理器收到的记录补充编号；不修改正文，不读取业务参数。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        record.operation_id = operation_id.get()
        return True
