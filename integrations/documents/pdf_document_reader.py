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
        # missing保存最终仍无文字的真实页码，ocr_pages保存尝试过OCR的页码。
        # 执行过OCR不代表识别一定成功，也可能是空白页，因此两组页码可能重叠。
        missing: list[int] = []
        ocr_pages: list[int] = []
        # enumerate逐项取得文字并生成编号；start=1让number对应用户看到的PDF页码。
        # 例如第5次循环number=5，而不是Python序列使用的下标4。
        for number, native_text in enumerate(texts, start=1):
            text = native_text
            if not text.strip() and self._recognizer is not None and self._renderer is not None:
                logger.debug("event=pdf_ocr_page_start pdf_page=%d", number)
                try:
                    # pages=[number]只请求当前这一页，不是渲染全部PDF。
                    # 例如number=5，返回images中唯一一张图片就是PDF第5页。
                    rendered = self._renderer.render(pdf_bytes=content, pages=[number], dpi=144)
                    # 检查“数量为1”及“图片对应页码正确”，防止错页引用。
                    # or会短路：数量不是1时，不再访问images[0]，空集合也不会越界。
                    if len(rendered.images) != 1 or rendered.images[0].page_number != number:
                        raise PdfRenderError("页面渲染结果与请求页码不一致。")
                    # Python集合下标从0开始，[0]取本次返回的第一张图片，
                    # 不表示PDF第1页。number=5时，这张图片的page_number仍为5。
                    # 外层循环依次换number，因此能处理多页，每次只持有一页图片。
                    image = rendered.images[0]
                    # png_bytes是当前页PNG文件的完整字节，不是路径或PDF原始内容。
                    result = self._recognizer.recognize(image_bytes=image.png_bytes)
                    # 只把各文字区域拼接后的正文交给后续内容构造器，不保存坐标或图片。
                    text = result.text
                    # append把真实页码追加到列表；空白识别结果也计入“执行过OCR”。
                    ocr_pages.append(number)
                    logger.debug("event=pdf_ocr_page_result pdf_page=%d character_count=%d", number, len(text))
                    # del移除这几个局部变量的引用，不删除磁盘文件，也不销毁OCR引擎。
                    # 已保存在text中的字符串仍可使用；没有其他引用时，大对象可被回收。
                    # 这不保证操作系统立刻收回同等内存；下一页识别仍复用self._recognizer。
                    del result, image, rendered
                except (OcrError, PdfRenderError) as error:
                    # 将渲染/OCR的错误转成文件读取错误，供API统一返回，不当空白跳过。
                    # from error保留原异常关联，日志可查安全调用位置；对外只返回固定提示。
                    # 原生提取、渲染及OCR下层也记录生命周期，不在这里打印异常原文。
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
