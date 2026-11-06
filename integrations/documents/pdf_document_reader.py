"""PDFium文字读取；与页面渲染共享锁，不调用视觉模型或OCR。"""

from contextlib import closing

import pypdfium2 as pdfium

from diagnostics.operation_logging import log_operation
from domain.documents.document_content_builder import DocumentContentBuilder
from domain.documents.document_reader_contract import DocumentReadError
from integrations.documents.pdfium_runtime import PDFIUM_LOCK
from models.documents.document_content import DocumentContent, DocumentReadLimits


class PdfDocumentReader:
    """每页一个块；只保留真实PDF页码，原生资源在read结束前关闭。"""

    @log_operation("document.read_pdf")
    def read(self, *, content: bytes, limits: DocumentReadLimits) -> DocumentContent:
        """读取可提取文字；损坏/加密失败明确报错，无文字页单独返回位置。"""
        builder = DocumentContentBuilder(limits)
        missing = []
        try:
            with PDFIUM_LOCK, pdfium.PdfDocument(content) as document:
                count = len(document)
                if count > limits.max_blocks:
                    raise DocumentReadError("document_limit_exceeded", "PDF页数超过DOCUMENT_MAX_BLOCKS限制。")
                for index in range(count):
                    # 页面及文字句柄没有实现with协议；closing在退出时调用close，
                    # 保证文字句柄先于页面和文档释放，包括提取失败的情况。
                    with closing(document[index]) as page, closing(page.get_textpage()) as text_page:
                        text = text_page.get_text_bounded()
                    if not text.strip():
                        missing.append(index + 1)
                    builder.add(text=text, kind="page", location=f"第{index + 1}页", page=index + 1)
        except Exception as error:
            if isinstance(error, DocumentReadError):
                raise
            raise DocumentReadError("document_unreadable", "PDF无法读取，可能损坏或需要密码。") from None
        warnings = ("部分页面没有可提取文字，可能为空白、图片或扫描件；本次未执行OCR。",) if missing else ()
        return builder.finish(page_count=count, pages_without_text=tuple(missing), warnings=warnings)
