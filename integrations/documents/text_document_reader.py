"""纯文本/Markdown读取，不解释Markdown或执行其中代码。"""

from diagnostics.operation_logging import log_operation
from domain.documents.document_content_builder import DocumentContentBuilder
from domain.documents.document_reader_contract import DocumentReadError
from domain.documents.text_decoding import decode_document_text
from models.documents.document_content import DocumentContent, DocumentReadLimits


class TextDocumentReader:
    """无文件句柄，只读取调用方提供的字节；TXT和MD共用此实现。"""

    @log_operation("document.read_text")
    def read(self, *, content: bytes, limits: DocumentReadLimits) -> DocumentContent:
        """返回一个完整正文块，不把空白或二进制替换成猜测文字。"""
        try:
            text = decode_document_text(content)
        except (UnicodeError, ValueError):
            raise DocumentReadError("document_unreadable", "文本编码不可读、为空白或包含二进制控制字符。") from None
        builder = DocumentContentBuilder(limits)
        builder.add(text=text, kind="text", location="全文")
        return builder.finish()
