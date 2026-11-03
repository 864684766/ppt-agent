"""隔离网页业务与HTTP实现；异常只包含可公开的错误说明。"""

from typing import Protocol

from models.web.webpage_content import WebpageContent


class WebpageReadError(RuntimeError):
    """无法取得可用网页文本；不得携带响应原文、凭据或请求头。"""


class WebpageReader(Protocol):
    """连接生命周期属于外层；实现可替换为其他读取后端。"""

    async def read(self, *, url: str) -> WebpageContent:
        """读取一个网页，失败抛WebpageReadError，取消继续向上传播。"""
        ...
