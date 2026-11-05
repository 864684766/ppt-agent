"""验证日志的行为和安全边界；不恢复用户删除的PDF错误场景测试。

本文件只测试诊断基础设施，不调用模型、真实网络或Office。
"""

import asyncio
import logging
from contextlib import aclosing

import httpx
import pytest

from api.request_logging_middleware import RequestLoggingMiddleware
from diagnostics.log_context import operation_id, request_id
from diagnostics.operation_logging import log_operation


def test_failed_operation_logs_location_without_sensitive_text(caplog) -> None:
    """异常原文和参数都不应写入日志，但错误类型和代码位置必须可查。"""
    @log_operation("test.failure")
    def failing_function(private_input: str) -> None:
        try:
            raise OSError(private_input)
        except OSError:
            raise RuntimeError(private_input) from None

    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
        failing_function("SECRET-private-body")
    assert "event=start operation=test.failure" in caplog.text
    assert "event=failed operation=test.failure" in caplog.text
    assert "RuntimeError[" in caplog.text and "OSError[" in caplog.text
    assert "test_operation_logging.py:" in caplog.text
    assert "SECRET-private-body" not in caplog.text
    assert operation_id.get() == "-"


@pytest.mark.asyncio
async def test_stream_cancellation_is_not_reported_as_success(caplog) -> None:
    """流式函数直到消费结束才完成；主动关闭时释放上游并记录取消。"""
    closed = []

    @log_operation("test.stream")
    async def stream():
        try:
            yield "first"
            yield "second"
        finally:
            closed.append(True)

    with caplog.at_level(logging.INFO):
        async with aclosing(stream()) as chunks:
            assert await anext(chunks) == "first"
    assert closed == [True]
    assert "event=cancelled operation=test.stream" in caplog.text
    assert "event=completed operation=test.stream" not in caplog.text
    assert operation_id.get() == "-"


@pytest.mark.asyncio
async def test_async_cancellation_propagates_and_logs(caplog) -> None:
    """取消不能被日志包装吞掉或转换成一般错误。"""
    @log_operation("test.cancel")
    async def cancelled():
        raise asyncio.CancelledError()

    with caplog.at_level(logging.INFO), pytest.raises(asyncio.CancelledError):
        await cancelled()
    assert "event=cancelled operation=test.cancel" in caplog.text
    assert "event=failed operation=test.cancel" not in caplog.text


@pytest.mark.asyncio
async def test_concurrent_http_requests_have_isolated_ids(caplog) -> None:
    """两个并发请求有独立编号，响应头可核对；URL参数和正文不记录。"""
    observed = []

    async def endpoint(scope, receive, send):
        current_id = request_id.get()
        observed.append(current_id)
        await asyncio.sleep(0)
        assert request_id.get() == current_id
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = RequestLoggingMiddleware(endpoint)
    with caplog.at_level(logging.INFO):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = await asyncio.gather(
                client.post("/test?token=SECRET_QUERY", content="SECRET_BODY"),
                client.post("/test?token=SECRET_QUERY", content="SECRET_BODY"),
            )
    identifiers = [response.headers["x-request-id"] for response in responses]
    assert len(set(identifiers)) == 2
    assert set(identifiers) == set(observed)
    assert request_id.get() == "-"
    assert "SECRET_QUERY" not in caplog.text and "SECRET_BODY" not in caplog.text
    assert "event=http_result" in caplog.text


def test_file_log_has_context_and_suppresses_sdk_debug(tmp_path) -> None:
    """真实写临时日志文件，检查关联字段和SDK调试正文不会随应用DEBUG开启。"""
    from config.logging_config import configure_logging

    root = logging.getLogger()
    original_level = root.level
    original_handlers = tuple(root.handlers)
    for handler in original_handlers:
        if handler.name in {"ppt-agent.file", "ppt-agent.console"}:
            root.removeHandler(handler)
    context_token = request_id.set("test-request")
    try:
        path = configure_logging(directory=tmp_path, level="DEBUG", output="file")

        @log_operation("test.file")
        def operation() -> None:
            logging.getLogger("openai").debug("SECRET_SDK_BODY")

        operation()
        assert path is not None
        content = path.read_text(encoding="utf-8")
        assert "request_id=test-request" in content
        assert " | operation_id=- | " not in content
        assert "event=completed operation=test.file duration_ms=" in content
        assert "SECRET_SDK_BODY" not in content
    finally:
        request_id.reset(context_token)
        for handler in tuple(root.handlers):
            if handler not in original_handlers:
                root.removeHandler(handler)
                handler.close()
        for handler in original_handlers:
            if handler not in root.handlers:
                root.addHandler(handler)
        root.setLevel(original_level)
