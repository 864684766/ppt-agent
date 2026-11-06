"""PDF文字读取与可选OCR回退；通过协议组合能力，不绑定具体OCR引擎。"""

from contextlib import closing
import logging

import pypdfium2 as pdfium

from diagnostics.operation_logging import log_operation
from domain.documents.document_content_builder import DocumentContentBuilder
from domain.documents.document_reader_contract import DocumentReadError
from domain.ocr.image_text_recognizer_contract import ImageTextRecognizer, OcrError
from domain.templates.pdf_page_renderer_contract import PdfPageRenderer, PdfRenderError
from integrations.documents.pdfium_runtime import PDFIUM_LOCK
from models.documents.document_content import DocumentContent, DocumentReadLimits

logger = logging.getLogger(__name__)


class PdfDocumentReader:
    """每个非空页面一个正文块；页码始终来自原PDF，不由OCR猜测。

    不注入依赖时仍能独立提取原生文字；OCR和页面渲染器必须成对提供。
    调用方负责组装实现与模型目录，本类不读取环境变量、不下载模型或写磁盘。
    """

    def __init__(
        self, *, recognizer: ImageTextRecognizer | None = None,
        renderer: PdfPageRenderer | None = None,
    ) -> None:
        if (recognizer is None) != (renderer is None):
            raise ValueError("PDF的OCR识别器和页面渲染器必须同时提供或同时省略。")
        self._recognizer = recognizer
        self._renderer = renderer

    @log_operation("document.read_pdf")
    def read(self, *, content: bytes, limits: DocumentReadLimits) -> DocumentContent:
        """先提取文字层，关闭PDF原生句柄后，对无文字页逐页渲染并OCR。

        先释放PDFIUM_LOCK再调用渲染器：渲染器也会获取同一把锁，持锁调用
        会死锁。OCR CPU计算不占用PDFium锁，不阻塞其他PDF原生操作。
        每次只持有一页图片，不一次渲染整份扫描PDF。现有渲染器每次会重新
        打开PDF，这是当前复用接口的代价，后续有性能证据再优化。
        """
        texts = self._read_native_pages(content=content, limits=limits)
        builder = DocumentContentBuilder(limits)
        missing: list[int] = []
        ocr_pages: list[int] = []
        for number, native_text in enumerate(texts, start=1):
            text = native_text
            if not text.strip() and self._recognizer is not None and self._renderer is not None:
                logger.debug("event=pdf_ocr_page_start pdf_page=%d", number)
                try:
                    rendered = self._renderer.render(pdf_bytes=content, pages=[number], dpi=144)
                    if len(rendered.images) != 1 or rendered.images[0].page_number != number:
                        raise PdfRenderError("页面渲染结果与请求页码不一致。")
                    image = rendered.images[0]
                    result = self._recognizer.recognize(image_bytes=image.png_bytes)
                    text = result.text
                    ocr_pages.append(number)
                    logger.debug("event=pdf_ocr_page_result pdf_page=%d character_count=%d", number, len(text))
                    # 图片和区域结果不进入DocumentContent，及时解除本页大对象引用。
                    del result, image, rendered
                except (OcrError, PdfRenderError) as error:
                    # 已在下层记录安全错误位置；对外统一语义，不把失败伪装成空白。
                    raise DocumentReadError(
                        "document_ocr_failed", f"PDF第{number}页OCR失败，请检查本地模型、页面大小及运行日志。",
                    ) from error
            if not text.strip():
                missing.append(number)
            # OCR和原生文字共用正文上限；超限明确失败，不截断、不交付半份内容。
            builder.add(text=text, kind="page", location=f"第{number}页", page=number)
        warnings: list[str] = []
        if ocr_pages:
            warnings.append("PDF部分无原生文字页已执行本地OCR；识别可能错字、漏字或阅读顺序不准确，请核对原文。")
        if missing:
            warnings.append(
                "部分页面在文字提取与OCR后仍无可读文字，可能为空白或未识别成功。"
                if self._recognizer is not None else
                "部分页面没有可提取文字，可能为空白、图片或扫描件；本次未配置OCR。"
            )
        logger.info("event=pdf_read_result total_pages=%d ocr_pages=%d pages_without_text=%d", len(texts), len(ocr_pages), len(missing))
        return builder.finish(page_count=len(texts), pages_without_text=tuple(missing), warnings=tuple(warnings))

    @staticmethod
    def _read_native_pages(*, content: bytes, limits: DocumentReadLimits) -> tuple[str, ...]:
        """在PDFium锁内只执行原生提取，限额预检查并关闭全部资源。"""
        texts: list[str] = []
        characters = 0
        try:
            with PDFIUM_LOCK, pdfium.PdfDocument(content) as document:
                if len(document) > limits.max_blocks:
                    raise DocumentReadError("document_limit_exceeded", "PDF页数超过DOCUMENT_MAX_BLOCKS限制。")
                for index in range(len(document)):
                    with closing(document[index]) as page, closing(page.get_textpage()) as text_page:
                        text = text_page.get_text_bounded()
                    characters += len(text)
                    if characters > limits.max_characters:
                        raise DocumentReadError("document_limit_exceeded", "读取文字超过DOCUMENT_MAX_CHARACTERS限制。")
                    texts.append(text)
        except DocumentReadError:
            raise
        except Exception:
            raise DocumentReadError("document_unreadable", "PDF无法读取，可能损坏或需要密码。") from None
        return tuple(texts)
