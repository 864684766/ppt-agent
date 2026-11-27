"""仅在HTTP明确需要备用读取时调用浏览器，不改变工具返回契约。"""

import logging

from domain.web.webpage_reader_contract import BrowserFallbackError, WebpageReader
from models.web.webpage_content import WebpageContent

logger = logging.getLogger(__name__)


class FallbackWebpageReader:
    """依次使用HTTP和浏览器读取器；依赖及资源生命周期由调用方管理。"""

    def __init__(self, *, primary: WebpageReader, browser: WebpageReader) -> None:
        self._primary = primary
        self._browser = browser

    async def read(self, *, url: str) -> WebpageContent:
        """HTTP被拒绝或无正文时尝试浏览器；其他错误按原契约传播。"""
        try:
            return await self._primary.read(url=url)
        except BrowserFallbackError:
            logger.info("event=webpage_browser_fallback")
            return await self._browser.read(url=url)
