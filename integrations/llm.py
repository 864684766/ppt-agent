"""模型适配层：把 LangChain/OpenAI 的细节隔离在 HTTP 接口之外。"""

from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Protocol, cast

import httpx
from langchain.messages import AIMessageChunk
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIError, APITimeoutError

from config.settings import Settings


class ModelConfigurationError(ValueError):
    """必要的模型配置缺失；健康检查仍可独立使用。"""


class ModelCallError(Exception):
    """可公开的调用错误；不携带代理原始响应、密钥或请求正文。"""

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out


class ChatClient(Protocol):
    """接口只依赖这份行为约定，测试时可用不联网的假客户端替换。"""

    def stream_reply(self, message: str) -> AsyncGenerator[str, None]:
        """返回可 aclose 的异步生成器，便于调用方在取消时释放上游连接。"""
        ...


class LangChainChatClient:
    """普通文本对话适配器；此阶段不保存历史、不调用工具。"""

    def __init__(self, model: ChatOpenAI) -> None:
        self._model = model

    async def stream_reply(self, message: str) -> AsyncGenerator[str, None]:
        """逐段交付正文，不在服务端拼接完整回答。

        async def 中包含 yield，得到的是异步生成器，应使用 async for 消费。
        模型的一个 chunk 可能包含多个 token；token、字符和 UTF-8 字节并不一一对应。
        不逐块 strip，因为空格和换行可能是 Markdown、代码或句子的一部分。
        """
        has_visible_text = False
        try:
            # 当前锁定版本的 ChatOpenAI.astream 源码是包含 yield 的 async def，
            # 实际返回 AsyncGenerator，具有 aclose；但公开注解只写 AsyncIterator。
            # cast 将已核实的具体类型告知 IDE，不创建对象，也不改变运行行为。
            # 若以后替换模型实现，应重新确认它仍支持 aclose。
            upstream = cast(
                AsyncGenerator[AIMessageChunk, None],
                self._model.astream([("human", message)]),
            )
            # 在正常结束、异常或取消时，主动关闭尚未消费完的上游生成器。
            async with aclosing(upstream) as chunks:
                async for chunk in chunks:
                    text = chunk.text
                    if text:
                        has_visible_text = has_visible_text or bool(text.strip())
                        yield text
        except APITimeoutError:
            raise ModelCallError("模型响应超时，请稍后重试。", timed_out=True) from None
        except APIConnectionError:
            raise ModelCallError("无法连接模型服务，请检查代理地址和网络。") from None
        except APIError:
            raise ModelCallError("模型服务调用失败，请检查密钥、模型名称或服务状态。") from None

        if not has_visible_text:
            raise ModelCallError("模型未返回可用的文本回答。")


def create_chat_client(
    settings: Settings, http_client: httpx.AsyncClient
) -> ChatClient:
    """使用默认模型创建客户端；这里只组装对象，不发起模型请求。

    http_client 由调用方管理生命周期。后续任务专用模型复用配置选择规则，
    本调试接口仅使用 LLM_MODEL，避免混淆普通对话和大纲任务。
    """
    if not all((settings.llm_base_url, settings.llm_api_key.get_secret_value(), settings.llm_model)):
        raise ModelConfigurationError("请配置 LLM_BASE_URL、LLM_API_KEY 和 LLM_MODEL。")
    try:
        endpoint = httpx.URL(settings.llm_base_url)
    except httpx.InvalidURL:
        raise ModelConfigurationError("LLM_BASE_URL 必须是有效的 HTTP 或 HTTPS 基础地址。") from None
    if endpoint.scheme not in ("http", "https") or not endpoint.host:
        raise ModelConfigurationError("LLM_BASE_URL 必须是有效的 HTTP 或 HTTPS 基础地址。")

    model = ChatOpenAI(
        base_url=settings.llm_base_url,
        # 当前版本接受 SecretStr；直接传入，避免提前展开成明文字符串。
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout_seconds,
        # 学习阶段一次请求只尝试一次，便于理解错误和控制调用次数。
        max_retries=0,
        max_tokens=settings.llm_max_tokens,
        http_async_client=http_client,
        # 固定使用 OpenAI 兼容的 Chat Completions 接口。
        use_responses_api=False,
    )
    return LangChainChatClient(model)
