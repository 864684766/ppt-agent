"""将 SearXNG 的 HTTP 搜索接口适配为项目的 WebSearchClient 协议。

本模块不读取环境变量，不依赖 LangChain，也不判断网页内容是否切题。
连接由调用方创建和关闭，因此单元测试可以直接注入 HTTP 替身。
"""

from hashlib import sha256
from urllib.parse import urlsplit

import httpx

from domain.web.web_search_contract import WebSearchError
from models.web.web_search_candidate import WebSearchCandidate


class SearxngSearchClient:
    """一次调用执行一次普通网页搜索；不重试、不翻页、不抓取网页正文。"""

    def __init__(
        self, *, client: httpx.AsyncClient, base_url: str,
        engines: str = "sogou", timeout_seconds: float = 30,
    ) -> None:
        """保存外层配置，不创建连接或立即搜索。

        client：借用的异步 HTTP 连接，生命周期属于调用方。
        base_url：SearXNG 根地址，可含部署子路径，不是某个结果网页。
        engines：逗号分隔的普通网页引擎 name；空字符串使用服务器默认配置。
        timeout_seconds：HTTP 各阶段等待超时秒数，不是整个 Agent 的时限。
        配置无效抛 ValueError；搜索失败统一抛不含上游原文的 WebSearchError。
        """
        address = base_url.strip().rstrip("/")
        parts = urlsplit(address)
        if (parts.scheme not in {"http", "https"} or not parts.hostname
                or parts.query or parts.fragment or parts.username or parts.password):
            raise ValueError("请配置有效的 SearXNG 根地址，不含查询参数、片段或账号密码。")
        if not 0 < timeout_seconds <= 120:
            raise ValueError("搜索超时秒数必须大于0且不超过120。")
        self._client = client
        self._search_url = address + "/search"
        self._engines = ",".join(name.strip() for name in engines.split(",") if name.strip())
        self._timeout_seconds = timeout_seconds

    async def search(self, *, query: str, max_results: int) -> tuple[WebSearchCandidate, ...]:
        """请求 JSON，再转换为统一候选；取消异常不捕获，由调用栈传播。"""
        # categories=general 避免把图片、视频列表混进普通网页结果。
        # SearXNG 没有这里所需的统一条数参数，max_results 在解析后本地截取。
        params = {"q": query, "format": "json", "categories": "general"}
        if self._engines:
            params["engines"] = self._engines
        try:
            response = await self._client.get(
                self._search_url, params=params, timeout=self._timeout_seconds,
                headers={"Accept": "application/json"}, follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            raise WebSearchError("搜索服务响应超时，请稍后重试。") from None
        except httpx.HTTPStatusError:
            raise WebSearchError("搜索服务返回异常状态，请检查服务及 JSON 接口配置。") from None
        except httpx.RequestError:
            raise WebSearchError("无法连接搜索服务，请检查地址和网络。") from None
        try:
            payload = response.json()
        except ValueError:
            raise WebSearchError("搜索服务未返回有效 JSON，请检查 JSON 接口配置。") from None
        return parse_searxng_results(payload, max_results=max_results)


def parse_searxng_results(payload: object, *, max_results: int) -> tuple[WebSearchCandidate, ...]:
    """只做供应商数据转换，保留上游顺序；不将 score 当成语义相似度。

    跳过无有效 HTTP(S) 地址的条目，按去首尾空白后的完整 URL 去重。
    不移除 URL 查询参数，以免把不同文章误合并。标题/摘要缺失时使用空字符串。
    无候选且引擎报告故障时明确报错，避免将服务故障伪装成正常零命中。
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise WebSearchError("搜索服务返回结构异常：缺少 results 列表。")
    candidates: list[WebSearchCandidate] = []
    seen_urls: set[str] = set()
    for item in payload["results"]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str):
            continue
        url = url.strip()
        try:
            parts = urlsplit(url)
            valid_url = parts.scheme in {"http", "https"} and bool(parts.hostname)
        except ValueError:
            valid_url = False
        if not valid_url or url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append(WebSearchCandidate(
            candidate_id="web_" + sha256(url.encode("utf-8")).hexdigest(),
            title=item["title"].strip() if isinstance(item.get("title"), str) else "",
            url=url,
            snippet=item["content"].strip() if isinstance(item.get("content"), str) else "",
        ))
        if len(candidates) >= max_results:
            break
    if not candidates and payload.get("unresponsive_engines"):
        raise WebSearchError("本次未获得可用网页，且搜索引擎报告故障，请检查 SearXNG。")
    return tuple(candidates)
