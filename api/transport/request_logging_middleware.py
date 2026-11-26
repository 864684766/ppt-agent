"""原生ASGI请求日志；覆盖SSE整个发送周期，不读取请求体或响应正文。"""

import logging
from time import perf_counter
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from diagnostics.log_context import request_id
from diagnostics.operation_logging import operation_scope


logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """服务器生成请求编号并放入X-Request-ID响应头，不信任外部传入编号。

    不使用BaseHTTPMiddleware，避免额外打断上下文传播或缓冲流式正文。
    HTTP状态200不代表SSE内模型调用成功，需结合模型和sse_error日志判断。
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        identifier = uuid4().hex
        token = request_id.set(identifier)
        status_code: int | None = None
        completed = False
        disconnected = False
        started = perf_counter()

        async def receive_with_status() -> Message:
            nonlocal disconnected
            message = await receive()
            if message["type"] == "http.disconnect":
                disconnected = True
            return message

        async def send_with_id(message: Message) -> None:
            nonlocal status_code, completed
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"x-request-id"]
                message = {**message, "headers": [*headers, (b"x-request-id", identifier.encode("ascii"))]}
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                completed = True

        try:
            with operation_scope(logger, "http.request"):
                try:
                    await self._app(scope, receive_with_status, send_with_id)
                finally:
                    # 记录路由模板而非原始URL/查询串，避免参数或资料编号泄露。
                    route = scope.get("route")
                    route_name = getattr(route, "path", "unmatched")
                    level = logging.INFO
                    if status_code is not None and status_code >= 500:
                        level = logging.ERROR
                    elif status_code is not None and status_code >= 400:
                        level = logging.WARNING
                    logger.log(
                        level, "event=http_result route=%s status=%s response_complete=%s disconnected=%s duration_ms=%.2f",
                        route_name, status_code, completed, disconnected, (perf_counter() - started) * 1000,
                    )
        finally:
            request_id.reset(token)
