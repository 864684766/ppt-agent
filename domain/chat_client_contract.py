"""模型对话契约：仅依赖 Python 标准库，可供 HTTP、工作流或脚本复用。

此模块定义调用方需要的行为和可公开错误，不创建客户端、不读取配置，
也不导入 FastAPI、LangChain、OpenAI 或具体适配器。
"""

from collections.abc import AsyncGenerator
from typing import Protocol


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


