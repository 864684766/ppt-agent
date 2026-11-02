"""模型适配层：把 LangChain/OpenAI 的细节隔离在 HTTP 接口之外。"""

from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import cast

import httpx
from langchain.messages import AIMessageChunk
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIError, APITimeoutError
from pydantic import SecretStr

from domain.chat import ChatClient, ModelCallError


class ModelConfigurationError(ValueError):
    """模型连接参数缺失或无效，由组装层转换为对应入口的错误。"""


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
    *,
    base_url: str,
    api_key: SecretStr,
    model_name: str,
    timeout_seconds: float,
    max_tokens: int,
    http_client: httpx.AsyncClient,
) -> ChatClient:
    """通过显式参数创建适配器，不依赖本项目的 Settings 或 .env 路径。

    Args:
        base_url: OpenAI 兼容代理基础地址，须包含供应商要求的基础路径。
        api_key: 密钥包装对象，避免常规打印时展开明文。
        model_name: 调用方已选定的模型；工厂不决定任务路由。
        timeout_seconds: 上游请求超时秒数，不是整个流的总时限。
        max_tokens: 本次输出 token 上限，仍须满足实际模型限制。
        http_client: 调用方拥有并负责关闭的异步 HTTP 客户端。

    Returns:
        满足 ChatClient 契约的适配器；创建时不发送模型请求。

    Raises:
        ModelConfigurationError: 必填连接参数缺失或基础地址无效。

    配置来源和客户端生命周期由外层组装。独立脚本可直接传参复用，
    无需携带 FastAPI、Settings 或项目目录；仍需安装本适配器的 SDK 依赖。
    """
    if not all((base_url, api_key.get_secret_value(), model_name)):
        raise ModelConfigurationError("模型基础地址、密钥和模型名称不能为空。")
    try:
        endpoint = httpx.URL(base_url)
    except httpx.InvalidURL:
        raise ModelConfigurationError("模型基础地址必须是有效的 HTTP 或 HTTPS 地址。") from None
    if endpoint.scheme not in ("http", "https") or not endpoint.host:
        raise ModelConfigurationError("模型基础地址必须是有效的 HTTP 或 HTTPS 地址。")

    model = ChatOpenAI(
        base_url=base_url,
        # 当前版本接受 SecretStr；直接传入，避免提前展开成明文字符串。
        api_key=api_key,
        model=model_name,
        timeout=timeout_seconds,
        # 学习阶段一次请求只尝试一次，便于理解错误和控制调用次数。
        max_retries=0,
        max_tokens=max_tokens,
        http_async_client=http_client,
        # 固定使用 OpenAI 兼容的 Chat Completions 接口。
        use_responses_api=False,
    )
    return LangChainChatClient(model)
