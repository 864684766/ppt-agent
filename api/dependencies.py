"""HTTP 依赖组装：连接配置、外部客户端与路由。"""

from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from config.settings import Settings
from domain.chat import ChatClient
from integrations.llm import ModelConfigurationError, create_chat_client


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
            # 这里是组装边界：将项目配置映射为适配器参数。
            # 适配器本身不知道 Settings、.env 或 FastAPI 的存在。
            client = create_chat_client(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model_name=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_tokens=settings.llm_max_tokens,
                http_client=http_client,
            )
        except ModelConfigurationError as error:
            raise HTTPException(503, str(error)) from None
        yield client
