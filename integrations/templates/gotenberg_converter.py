"""Gotenberg的PPTX转PDF适配器，不依赖Settings、FastAPI或Agent框架。"""

import logging

import math

import httpx

from diagnostics.operation_logging import log_operation
from domain.templates.presentation_pdf_converter_contract import PresentationConversionError


logger = logging.getLogger(__name__)


class GotenbergPdfConverter:
    """将一个PPTX作为multipart文件上传，检查结果后返回PDF字节。

    本类只处理服务接入：不扫描目录、不写PDF、不生成图片、不调用模型。
    client由外层创建并关闭，方便多个转换共用连接池，也避免隐藏的资源泄漏。
    """

    def __init__(
        self, *, client: httpx.AsyncClient, base_url: str, timeout_seconds: float = 120,
    ) -> None:
        """保存连接配置；创建实例时不会请求/health或上传文件。

        base_url：HTTP(S)服务根地址，可包含反向代理的子路径，但不能带
        查询参数、片段或内嵌账号密码；接口路径由本类统一拼接。
        timeout_seconds：HTTP各阶段等待上限，单位秒；不是整个任务总时限。
        服务端还有自己的API超时，本参数不能覆盖服务端配置。
        配置格式错误抛ValueError，实际转换失败抛PresentationConversionError。
        """
        try:
            address = httpx.URL(base_url.strip().rstrip("/"))
        except httpx.InvalidURL:
            raise ValueError("请配置有效的Gotenberg HTTP(S)根地址。") from None
        if (address.scheme not in {"http", "https"} or not address.host
                or address.query or address.fragment or address.username or address.password):
            raise ValueError("Gotenberg根地址不能包含查询参数、片段或账号密码。")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("转换等待超时必须为大于0的有限秒数。")
        self._client = client
        self._convert_url = str(address).rstrip("/") + "/forms/libreoffice/convert"
        self._timeout_seconds = timeout_seconds

    @log_operation("template.convert_pdf")
    async def convert(self, *, pptx_bytes: bytes, file_name: str) -> bytes:
        """发送一次转换请求，返回初步检查通过的PDF，不自动重试。

        async/await在等待网络时交还事件循环，不会启动本机LibreOffice。
        任务取消不在此捕获，调用方可以正常取消等待；取消HTTP请求不保证
        远程服务已停止转换。当前整份输入和输出放在内存，暂不支持流式大文件。
        """
        if (not pptx_bytes or not file_name.lower().endswith(".pptx")
                or any(char in file_name for char in ("/", "\\", "\r", "\n"))):
            raise PresentationConversionError("请提供非空PPTX内容和不含目录的.pptx文件名。")

        # multipart/form-data是上传文件的HTTP格式。files是Gotenberg规定的字段名，
        # 元组依次为“上传文件名、文件字节、文件媒体类型”。不要手动设置multipart
        # Content-Type：httpx会生成分隔各部分所需的boundary并写入请求头。
        logger.info("event=conversion_input input_bytes=%s timeout_seconds=%s", len(pptx_bytes), self._timeout_seconds)
        files = {"files": (
            file_name, pptx_bytes,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )}
        try:
            response = await self._client.post(
                self._convert_url, files=files, headers={"Accept": "application/pdf"},
                timeout=self._timeout_seconds, follow_redirects=False,
            )
            # 非成功状态抛HTTPStatusError，不把错误页面保存成.pdf。
            response.raise_for_status()
        except httpx.TimeoutException:
            raise PresentationConversionError("PPTX转换等待超时，请检查文档大小和服务排队情况。") from None
        except httpx.HTTPStatusError as error:
            # 只公开状态码，不转发上游错误正文（可能带有文档内容或内部路径）。
            status = error.response.status_code
            logger.warning("event=upstream_status service=gotenberg http_status=%s", status)
            raise PresentationConversionError(
                f"Gotenberg返回HTTP {status}，请检查文件、LibreOffice状态和服务端超时配置。"
            ) from None
        except httpx.RequestError:
            raise PresentationConversionError("无法连接Gotenberg，请检查服务地址和网络。") from None

        content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0].strip().lower()
        pdf_bytes = response.content
        # 三项只是基本格式检查：媒体类型、PDF文件头和尾部结束标记。
        # 不能证明每页内容正确、PDF无损坏或与WPS显示一致，仍需打开文件验收。
        if (content_type != "application/pdf" or not pdf_bytes.startswith(b"%PDF-")
                or b"%%EOF" not in pdf_bytes[-1024:]):
            raise PresentationConversionError("转换服务未返回符合基本格式的PDF，未保存结果。")
        logger.info("event=conversion_result http_status=%s output_bytes=%s", response.status_code, len(pdf_bytes))
        return pdf_bytes
