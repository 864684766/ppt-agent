"""HTTP 依赖组装：连接配置、外部客户端与路由。"""

from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from config.settings import Settings
from integrations.llm import ChatClient, ModelConfigurationError, create_chat_client


async def get_chat_client() -> AsyncIterator[ChatClient]:
    """每次请求创建客户端，请求结束或失败后释放网络连接。

    yield 把客户端交给 FastAPI 路由使用；路由执行结束后会继续退出
    async with 并关闭连接。测试可覆盖本依赖，完全绕开真实密钥和网络。
    当前不缓存 Settings，修改 .env 后下一次请求即可读取新配置。
    """
    try:
        settings = Settings()
    except ValidationError:
        # Pydantic 原始错误可能携带配置值，因此仅公开固定提示。
        raise HTTPException(503, "模型配置格式不正确，请检查本地环境变量。") from None

    async with httpx.AsyncClient() as http_client:
        try:
            client = create_chat_client(settings, http_client)
        except ModelConfigurationError as error:
            raise HTTPException(503, str(error)) from None
        yield client
