"""组装实际读取器；按格式选择，实现可通过小型Protocol替换。"""

from domain.documents.document_reader_contract import DocumentReader
from domain.ocr.image_text_recognizer_contract import ImageTextRecognizer
from domain.templates.pdf_page_renderer_contract import PdfPageRenderer
from integrations.documents.docx_document_reader import DocxDocumentReader
from integrations.documents.doc_document_reader import DocDocumentReader
from integrations.documents.pdf_document_reader import PdfDocumentReader
from integrations.documents.pptx_document_reader import PptxDocumentReader
from integrations.documents.text_document_reader import TextDocumentReader
from integrations.documents.xlsx_document_reader import XlsxDocumentReader


def create_document_readers(
    *, recognizer: ImageTextRecognizer | None = None, renderer: PdfPageRenderer | None = None,
    gotenberg_base_url: str = "", gotenberg_timeout_seconds: float = 120,
) -> dict[str, DocumentReader]:
    """组装读取器映射；可注入PDF的OCR能力，不读配置或加载模型。"""
    text_reader = TextDocumentReader()
    pdf_reader = PdfDocumentReader(recognizer=recognizer, renderer=renderer)
    return {"txt": text_reader, "md": text_reader, "pdf": pdf_reader,
            "doc": DocDocumentReader(base_url=gotenberg_base_url, timeout_seconds=gotenberg_timeout_seconds, pdf_reader=pdf_reader),
            "docx": DocxDocumentReader(), "xlsx": XlsxDocumentReader(), "pptx": PptxDocumentReader()}
