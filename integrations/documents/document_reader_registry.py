"""组装实际读取器；按格式选择，实现可通过小型Protocol替换。"""

from domain.documents.document_reader_contract import DocumentReader
from integrations.documents.docx_document_reader import DocxDocumentReader
from integrations.documents.pdf_document_reader import PdfDocumentReader
from integrations.documents.pptx_document_reader import PptxDocumentReader
from integrations.documents.text_document_reader import TextDocumentReader
from integrations.documents.xlsx_document_reader import XlsxDocumentReader


def create_document_readers() -> dict[str, DocumentReader]:
    """创建无状态读取器映射，不读取文件/配置，不连接模型或缓存用户内容。"""
    text_reader = TextDocumentReader()
    return {"txt": text_reader, "md": text_reader, "pdf": PdfDocumentReader(), "docx": DocxDocumentReader(), "xlsx": XlsxDocumentReader(), "pptx": PptxDocumentReader()}
