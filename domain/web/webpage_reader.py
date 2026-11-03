"""网页读取业务：校验输入并限制公开正文长度，不依赖HTTP或Agent框架。"""

from urllib.parse import urlsplit

from domain.web.webpage_reader_contract import WebpageReader
from models.web.webpage_content import WebpageReadResult


async def read_webpage(
    *, reader: WebpageReader, url: str, max_chars: int = 12000,
) -> WebpageReadResult:
    """读取URL并形成一次结果；不登记资料、不保存正文、不做相关性判断。

    参数错误抛ValueError，抓取失败由读取实现抛WebpageReadError。
    max_chars只限制返回文本，不改变HTTP下载字节上限。
    """
    if not isinstance(url, str) or not 1 <= len(url.strip()) <= 4096:
        raise ValueError("url必须是1至4096字符的网页地址。")
    address = url.strip()
    parts = urlsplit(address)
    if (parts.scheme not in {"http", "https"} or not parts.hostname
            or parts.username or parts.password):
        raise ValueError("只接受不包含账号密码的HTTP/HTTPS网页地址。")
    if type(max_chars) is not int or not 100 <= max_chars <= 50000:
        raise ValueError("max_chars必须为100至50000的整数。")
    page = await reader.read(url=address)
    text = page.text[:max_chars]
    return WebpageReadResult(
        requested_url=address, content=page, text=text,
        truncated=len(page.text) > max_chars,
    )
