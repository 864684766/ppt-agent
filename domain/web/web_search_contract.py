"""外部搜索能力协议与公开错误；不依赖HTTP库或配置。"""

from typing import Protocol

from models.web.web_search_candidate import WebSearchCandidate


class WebSearchError(RuntimeError):
    """搜索适配器提供的安全错误；不得包含密钥、请求头或上游响应原文。"""


class WebSearchClient(Protocol):
    """替换搜索供应商只需实现此方法；连接生命周期由外层调用方管理。"""

    async def search(self, *, query: str, max_results: int) -> tuple[WebSearchCandidate, ...]:
        """返回候选网页；失败抛WebSearchError，任务取消正常向上传递。"""
        ...
