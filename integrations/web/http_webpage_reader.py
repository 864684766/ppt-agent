"""静态网页HTTP适配器：有限下载、编码处理和HTML文本提取。"""

from datetime import datetime, timezone
import re
import ssl

import httpx

from domain.web.webpage_reader_contract import WebpageReadError
from integrations.web.html_text_extractor import HtmlTextExtractor
from models.web.webpage_content import WebpageContent


class HttpWebpageReader:
    """借用外层HTTP连接，不读取.env，不执行JavaScript，不绕过访问限制。"""

    def __init__(
        self, *, client: httpx.AsyncClient, timeout_seconds: float = 20,
        max_download_bytes: int = 2_000_000,
    ) -> None:
        """保存读取限制；连接由外层关闭，重定向上限由外层client配置。

        timeout_seconds是HTTP各阶段等待秒数；max_download_bytes是解压后
        HTML字节上限，防止把大附件或无限响应全部装入内存，不是正文字符数。
        """
        if not 0 < timeout_seconds <= 120:
            raise ValueError("网页读取超时必须大于0且不超过120秒。")
        if not 1024 <= max_download_bytes <= 10_000_000:
            raise ValueError("网页下载上限必须为1024至10000000字节。")
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_download_bytes = max_download_bytes

    async def read(self, *, url: str) -> WebpageContent:
        """读取一个HTML页面，失败抛安全错误；不捕获取消异常。"""
        try:
            async with self._client.stream(
                "GET", url, timeout=self._timeout_seconds, follow_redirects=True,
                headers={"Accept": "text/html,application/xhtml+xml", "User-Agent": "PptAgent/0.1"},
            ) as response:
                response.raise_for_status()
                media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if media_type not in {"text/html", "application/xhtml+xml"}:
                    raise WebpageReadError("目标不是HTML网页；当前不读取PDF、图片或其他附件。")
                # aiter_bytes返回解压后的数据；达到限制立即停止，退出上下文关闭响应。
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > self._max_download_bytes:
                        raise WebpageReadError("网页超过下载字节上限，请选择更小的页面。")
                    body.extend(chunk)
                final_url = str(response.url)
                header_encoding = response.charset_encoding
        except httpx.TimeoutException:
            raise WebpageReadError("网页读取超时，请稍后重试或选择其他来源。") from None
        except httpx.HTTPStatusError as error:
            raise WebpageReadError(f"网页返回HTTP {error.response.status_code}，无法读取。") from None
        except httpx.TooManyRedirects:
            raise WebpageReadError("网页重定向次数过多，无法读取。") from None
        except httpx.ConnectError as error:
            # 遍历异常链区分TLS校验失败，不把底层原文或请求信息公开。
            cause: BaseException | None = error
            while cause is not None:
                if isinstance(cause, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(cause):
                    raise WebpageReadError("网页HTTPS证书校验失败，请检查证书、代理或网页TLS校验配置。") from None
                cause = cause.__cause__
            raise WebpageReadError("无法连接网页，请检查网络或选择其他来源。") from None
        except httpx.RequestError:
            raise WebpageReadError("无法连接网页，请检查网络或选择其他来源。") from None

        html = decode_html(bytes(body), header_encoding=header_encoding)
        parser = HtmlTextExtractor()
        parser.feed(html)
        parser.close()
        title, text = parser.result()
        if not text:
            raise WebpageReadError("网页没有可提取文本，可能需要JavaScript、登录或其他读取方式。")
        return WebpageContent(
            final_url=final_url, title=title, text=text,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )


def decode_html(body: bytes, *, header_encoding: str | None) -> str:
    """优先HTTP编码，其次HTML声明，最后UTF-8；兼容常见中文GBK网页。

    不对整个页面做复杂编码猜测。遇到不可解码字符用替换字符保留其他内容。
    """
    declaration = re.search(br'charset\s*=\s*[\x22\x27]?\s*([a-zA-Z0-9_-]+)', body[:8192], re.I)
    encoding = header_encoding or (declaration.group(1).decode("ascii") if declaration else "utf-8-sig")
    if encoding.lower() in {"gb2312", "gbk"}:
        encoding = "gb18030"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
