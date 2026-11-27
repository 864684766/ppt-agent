"""使用本机Edge加载动态网页；每次读取使用独立浏览器上下文。"""

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError, async_playwright

from diagnostics.operation_logging import log_operation
from domain.web.webpage_reader_contract import WebpageReadError
from integrations.web.html_text_extractor import HtmlLinkExtractor, HtmlTextExtractor
from models.web.webpage_content import WebpageContent

logger = logging.getLogger(__name__)


class BrowserWebpageReader:
    """启动无界面Edge读取一个网页，不复用用户的登录信息或浏览器会话。"""

    def __init__(self, *, timeout_seconds: float, max_download_bytes: int) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_download_bytes = max_download_bytes

    @log_operation("web.browser_fetch")
    async def read(self, *, url: str) -> WebpageContent:
        """在线程内运行独立事件循环，兼容Windows服务中无法启动子进程的事件循环。"""
        return await asyncio.to_thread(lambda: asyncio.run(self._read_in_browser(url)))

    async def _read_in_browser(self, url: str) -> WebpageContent:
        try:
            # 单次总时限包括启动和关闭，避免页面持续加载导致任务无限等待。
            async with asyncio.timeout(self._timeout_seconds):
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(channel="msedge", headless=True)
                    try:
                        context = await browser.new_context(accept_downloads=False)
                        page = await context.new_page()
                        response = await page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_seconds * 1000)
                        if response is None or response.status >= 400:
                            status = response.status if response else "未知"
                            raise WebpageReadError(f"浏览器访问网页失败，HTTP状态：{status}。")
                        if urlsplit(page.url).scheme not in {"http", "https"}:
                            raise WebpageReadError("浏览器跳转到了不支持的地址。")
                        html = await page.content()
                        if len(html.encode("utf-8")) > self._max_download_bytes:
                            raise WebpageReadError("浏览器页面超过读取字节上限。")
                        parser = HtmlTextExtractor()
                        parser.feed(html)
                        parser.close()
                        title, text = parser.result()
                        links = HtmlLinkExtractor(page.url)
                        links.feed(html)
                        links.close()
                        if not text:
                            raise WebpageReadError("浏览器未提取到网页正文，可能需要登录或人工操作。")
                        logger.info("event=browser_webpage_result text_chars=%s link_count=%s", len(text), len(links.links))
                        return WebpageContent(final_url=page.url, title=title, text=text,
                                              fetched_at=datetime.now(timezone.utc).isoformat(), links=tuple(links.links))
                    finally:
                        await browser.close()
        except (TimeoutError, PlaywrightTimeoutError):
            raise WebpageReadError("浏览器读取网页超时，请稍后重试。") from None
        except PlaywrightError:
            raise WebpageReadError("浏览器读取失败，请确认本机已安装Microsoft Edge且网页可访问。") from None
