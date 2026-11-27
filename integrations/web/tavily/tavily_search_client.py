"""Tavily搜索HTTP适配器；不负责读取网页正文或判断资料可信度。"""

import logging
from hashlib import sha256
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from diagnostics.operation_logging import log_operation
from domain.web.web_search_contract import WebSearchError
from models.web.web_search_candidate import WebSearchCandidate

logger = logging.getLogger(__name__)


class TavilySearchClient:
    """借用调用方的HTTP连接；每次调用执行一次basic搜索，不自动重试。"""

    def __init__(self, *, client: httpx.AsyncClient, api_key: SecretStr, timeout_seconds: float = 30) -> None:
        """密钥只用于请求头；连接由调用方关闭，超时为HTTP各阶段秒数。"""
        if not 0 < timeout_seconds <= 120:
            raise ValueError("搜索超时秒数必须大于0且不超过120。")
        self._client = client
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    @log_operation("web.search")
    async def search(self, *, query: str, max_results: int) -> tuple[WebSearchCandidate, ...]:
        """返回转换后的网页候选；响应摘要不是已读取的正文。"""
        if not self._api_key.get_secret_value().strip():
            raise WebSearchError("请在本机配置TAVILY_API_KEY。")
        logger.info("event=search_input provider=tavily query_chars=%s max_results=%s", len(query), max_results)
        try:
            response = await self._client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": "Bearer " + self._api_key.get_secret_value()},
                json={"query": query, "max_results": max_results, "search_depth": "basic",
                      "include_answer": False, "include_raw_content": False, "auto_parameters": False},
                timeout=self._timeout_seconds, follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            raise WebSearchError("Tavily搜索超时，请稍后重试。") from None
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            logger.warning("event=upstream_status service=tavily http_status=%s", status)
            raise WebSearchError(f"Tavily搜索返回HTTP {status}，请检查密钥、额度或服务状态。") from None
        except httpx.RequestError:
            raise WebSearchError("无法连接Tavily搜索服务，请检查网络。") from None
        try:
            payload = response.json()
        except ValueError:
            raise WebSearchError("Tavily搜索未返回有效JSON。") from None
        candidates = parse_tavily_results(payload, max_results=max_results)
        logger.info("event=search_result provider=tavily returned_count=%s", len(candidates))
        return candidates


def parse_tavily_results(payload: object, *, max_results: int) -> tuple[WebSearchCandidate, ...]:
    """按URL去重并保留返回顺序；不将供应商评分解释为事实准确度。"""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise WebSearchError("Tavily搜索返回结构异常：缺少results列表。")
    items: list[WebSearchCandidate] = []
    seen: set[str] = set()
    for item in payload["results"]:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        url = item["url"].strip()
        try:
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or url in seen:
                continue
        except ValueError:
            continue
        seen.add(url)
        items.append(WebSearchCandidate(candidate_id="web_" + sha256(url.encode("utf-8")).hexdigest(), url=url,
            title=item["title"].strip() if isinstance(item.get("title"), str) else "",
            snippet=item["content"].strip() if isinstance(item.get("content"), str) else "", engines=()))
        if len(items) >= max_results:
            break
    return tuple(items)
