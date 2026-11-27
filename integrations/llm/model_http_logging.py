"""记录聊天模型请求的传输时间，供对照 Agent 的完整调用耗时。"""

import logging
from time import perf_counter

import httpx

logger = logging.getLogger(__name__)


async def log_model_request(request: httpx.Request) -> None:
    """HTTPX 已准备好请求，此时可以看到 SDK 实际传入的读取超时秒数。"""
    request.extensions["model_request_started"] = perf_counter()
    logger.info("event=model_http_start read_timeout_seconds=%s", request.extensions.get("timeout", {}).get("read"))


async def log_model_headers(response: httpx.Response) -> None:
    """此回调在收到响应头时触发，正文下载和模型输出解析可能仍未完成。"""
    started = response.request.extensions["model_request_started"]
    logger.info("event=model_http_headers status_code=%d elapsed_ms=%.2f",
                response.status_code, (perf_counter() - started) * 1000)
