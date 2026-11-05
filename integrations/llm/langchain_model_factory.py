"""统一构造OpenAI兼容的LangChain模型，不负责聊天或视觉业务。

工厂是普通函数：集中校验连接参数和SDK选项，避免各调用点重复构造。
不是全局单例；不同任务仍可传入不同模型名、超时和输出预算。
"""

import logging

import httpx
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from diagnostics.operation_logging import log_operation


logger = logging.getLogger(__name__)


class ModelConfigurationError(ValueError):
    """连接参数缺失或无效；由入口转换为HTTP错误或测试失败。"""


@log_operation("model.create")
def create_langchain_model(
    *, base_url: str, api_key: SecretStr, model_name: str,
    timeout_seconds: float, max_tokens: int, http_client: httpx.AsyncClient,
) -> ChatOpenAI:
    """创建可用于文本或多模态输入的模型，调用本函数不会发送请求。

    参数由调用方显式传入，本模块不读取.env，也不决定业务任务用哪个模型。
    base_url为供应商要求的HTTP(S)基础地址；api_key为遮蔽显示的密钥；
    model_name为当前任务模型名（名称不保证图片能力）；timeout_seconds为
    单次请求超时秒数；max_tokens为输出预算，不是输入字符数。
    http_client由调用方创建并关闭，模型工厂不拥有其生命周期。

    返回ChatOpenAI实例：聊天适配器可调用astream，视觉适配器可调用ainvoke。
    固定一次尝试、Chat Completions接口和系统代理兼容选项，统一连接行为。
    """
    if not all((base_url.strip(), api_key.get_secret_value().strip(), model_name.strip())):
        raise ModelConfigurationError("模型基础地址、密钥和模型名称不能为空。")
    try:
        endpoint = httpx.URL(base_url)
    except httpx.InvalidURL:
        raise ModelConfigurationError("模型基础地址必须是有效的HTTP或HTTPS地址。") from None
    if endpoint.scheme not in ("http", "https") or not endpoint.host:
        raise ModelConfigurationError("模型基础地址必须是有效的HTTP或HTTPS地址。")
    if timeout_seconds <= 0 or max_tokens <= 0:
        raise ModelConfigurationError("模型超时秒数和输出token预算必须大于0。")
    logger.debug("event=model_configuration model=%r timeout_seconds=%s max_tokens=%s", model_name, timeout_seconds, max_tokens)
    return ChatOpenAI(
        base_url=base_url, api_key=api_key, model=model_name,
        timeout=timeout_seconds, max_tokens=max_tokens, max_retries=0,
        http_async_client=http_client, use_responses_api=False,
        # 不由SDK另建带socket选项的transport，保留传入httpx的系统代理行为。
        http_socket_options=(),
    )
