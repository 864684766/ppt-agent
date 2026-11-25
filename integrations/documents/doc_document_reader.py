"""通过注入的 Gotenberg 将旧版 DOC 转为 PDF，再复用 PDF 读取器。"""

import httpx

from diagnostics.operation_logging import log_operation
from domain.documents.document_reader_contract import DocumentReadError, DocumentReader
from models.documents.document_content import DocumentContent, DocumentReadLimits


class DocDocumentReader:
    """同步转换与读取；调用方负责在线程执行，客户端由本次调用创建并关闭。"""

    def __init__(self, *, base_url: str, timeout_seconds: float, pdf_reader: DocumentReader) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._pdf_reader = pdf_reader

    @log_operation("document.read_doc")
    def read(self, *, content: bytes, limits: DocumentReadLimits) -> DocumentContent:
        """转换结果限制为50 MiB；转换或解析失败抛出明确的读取错误。"""
        if not self._base_url:
            raise DocumentReadError("document_unreadable", "读取DOC需要配置可用的Gotenberg服务。")
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                with client.stream("POST", self._base_url + "/forms/libreoffice/convert",
                                   files={"files": ("document.doc", content, "application/msword")}) as response:
                    response.raise_for_status()
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 50 * 1024 * 1024:
                            raise DocumentReadError("document_unreadable", "DOC转换结果超过50 MiB。")
        except httpx.HTTPError:
            raise DocumentReadError("document_unreadable", "DOC转换失败，请检查Gotenberg服务和文件。") from None
        if not data.startswith(b"%PDF-"):
            raise DocumentReadError("document_unreadable", "DOC转换服务未返回有效PDF。")
        result = self._pdf_reader.read(content=bytes(data), limits=limits)
        return result.model_copy(update={"warnings": (*result.warnings, "DOC经转换为PDF后提取，位置为转换后的页码；版式和内容可能与原文不同。")})
