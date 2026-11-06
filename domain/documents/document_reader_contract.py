"""不同格式读取器的统一调用约定。"""

from typing import Protocol

from models.documents.document_content import DocumentContent, DocumentReadLimits


class DocumentReadError(ValueError):
    """读取失败的固定分类和安全提示；不包含正文或底层解析异常原文。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DocumentReader(Protocol):
    """同步读取文件字节，返回统一内容；CPU/解析工作由异步入口在线程中调用。"""

    def read(self, *, content: bytes, limits: DocumentReadLimits) -> DocumentContent:
        """调用方提供完整字节和限额；实现负责关闭自己创建的解析资源。

        不读取.env、不调用大语言模型、不归档原文件；可注入本地OCR。无可靠文字时返回明确提示；损坏、
        加密或规模超限时抛DocumentReadError，不能返回伪造正文。
        """
        ...
