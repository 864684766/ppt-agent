"""真实网页备用读取：uv run --locked python -m pytest tests/test_browser_webpage_reader.py -s。"""

import pytest

from config.settings import Settings
from integrations.web.browser_webpage_reader import BrowserWebpageReader
from integrations.web.fallback_webpage_reader import FallbackWebpageReader
from integrations.web.http_webpage_reader import HttpWebpageReader
from integrations.web.webpage_http_client import create_webpage_http_client
from tools.web.fetch_webpage_tool import create_fetch_webpage_tool


@pytest.mark.asyncio
async def test_real_browser_webpage() -> None:
    """真实访问百度百科；结果和标题仍需人工确认，依赖本机Edge及网络。"""
    settings = Settings()
    url = "https://baike.baidu.com/item/%E3%80%8A%E4%B8%89%E5%9B%BD%E6%BC%94%E4%B9%89%E3%80%8B/7088688"
    async with create_webpage_http_client(verify_tls=settings.webpage_tls_verify) as client:
        reader = FallbackWebpageReader(
            primary=HttpWebpageReader(client=client, timeout_seconds=settings.webpage_timeout_seconds,
                                      max_download_bytes=settings.webpage_max_download_bytes),
            browser=BrowserWebpageReader(timeout_seconds=settings.webpage_timeout_seconds,
                                         max_download_bytes=settings.webpage_max_download_bytes),
        )
        result = await create_fetch_webpage_tool(reader=reader).ainvoke({"url": url, "max_chars": 50000})
    print("【标题】", result["title"])
    print("【正文字符数】", result["returned_chars"], "【链接数】", len(result["links"]))
    print("【正文预览】", result["text"][:500])
    assert "三国演义" in result["title"]
    assert result["returned_chars"] > 1000
