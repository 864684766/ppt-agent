"""通过PDFium绘制页面，通过Pillow编码PNG；不启动外部程序。"""

import logging

import hashlib
import math
from collections.abc import Sequence
from contextlib import ExitStack
from io import BytesIO
from threading import Lock

import pypdfium2 as pdfium

from diagnostics.operation_logging import log_operation
from domain.templates.pdf_page_renderer_contract import PdfRenderError
from models.templates.pdf_page_image import PdfPageImage, PdfRenderResult


logger = logging.getLogger(__name__)


# PDFium不是线程安全库：即使不同实例处理不同PDF，也不应同时调用。
# 该锁仅保护本模块在同一进程中的PDFium操作，不承载业务数据；多进程各自隔离。
# 其他代码也应通过本模块调用PDFium，不绕开锁自行操作。暂不实现多进程池。
_PDFIUM_LOCK = Lock()


class PdfiumPageRenderer:
    """可独立调用的同步渲染器。调用方负责读取PDF和保存返回图片。

    本模块不依赖Settings、网络、LLM或FastAPI。接入异步服务时可由外层用
    asyncio.to_thread调用render，避免阻塞事件循环；线程取消不立即中断底层绘制。
    """

    def __init__(self, *, max_page_pixels: int = 20_000_000) -> None:
        """设置单页像素上限，默认2000万像素；不是字节数或总文件大小上限。

        大页面与高DPI可能占用大量内存，因此在分配位图前检查。超限报错，
        不悄悄降低分辨率。调用方可显式调整上限，不增加尚无需求的环境变量。
        """
        if type(max_page_pixels) is not int or max_page_pixels <= 0:
            raise ValueError("单页像素上限必须为正整数。")
        self._max_page_pixels = max_page_pixels

    @log_operation("pdf.render")
    def render(
        self, *, pdf_bytes: bytes, pages: Sequence[int] | None = None, dpi: int = 144,
    ) -> PdfRenderResult:
        """校验参数→读取页数→渲染选定页→编码PNG→关闭所有底层资源。

        返回图片只在整次调用成功后交付，失败不会返回半份结果。
        全部图片会保存在内存；很长的PDF建议分批选择页码，当前不提供缓存或流式输出。
        """
        if not pdf_bytes:
            raise PdfRenderError("PDF内容不能为空。")
        if type(dpi) is not int or not 36 <= dpi <= 300:
            raise PdfRenderError("DPI必须为36至300之间的整数，默认144。")
        # 先复制序列，避免调用方在本次渲染过程中修改同一个列表。
        selected = tuple(pages) if pages is not None else None
        logger.info("event=render_input input_bytes=%s dpi=%s requested_pages=%s", len(pdf_bytes), dpi, len(selected) if selected is not None else "all")
        if selected is not None:
            # bool在Python中也是int的子类；用type(...) is int明确拒绝True/False。
            if not selected or any(type(number) is not int for number in selected):
                raise PdfRenderError("页码必须是非空整数序列，例如[1, 3]；None表示全部页。")
            if len(set(selected)) != len(selected):
                raise PdfRenderError("页码不能重复，请为每个页面只指定一次。")
        try:
            with _PDFIUM_LOCK, pdfium.PdfDocument(pdf_bytes) as document:
                total_pages = len(document)
                if total_pages == 0:
                    raise PdfRenderError("PDF没有可渲染的页面。")
                if selected is None:
                    selected = tuple(range(1, total_pages + 1))
                if any(number < 1 or number > total_pages for number in selected):
                    raise PdfRenderError(f"页码超出范围，当前PDF共{total_pages}页，页码从1开始。")
                images = tuple(self._render_page(document, number, dpi) for number in selected)
        except (pdfium.PdfiumError, OSError, ValueError, RuntimeError) as error:
            # 自己的公开错误保持原样；底层错误不透传，避免泄露PDF内容或内部信息。
            if isinstance(error, PdfRenderError):
                raise
            raise PdfRenderError("无法读取或渲染PDF，请确认文件未损坏、未加密且页面可读取。") from None
        logger.info("event=render_result total_pages=%s rendered_pages=%s", total_pages, len(images))
        return PdfRenderResult(
            pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(), total_pages=total_pages,
            dpi=dpi, images=images,
        )

    def _render_page(self, document: pdfium.PdfDocument, number: int, dpi: int) -> PdfPageImage:
        """绘制一页。下划线表示内部方法，调用方应使用render而不直接使用它。"""
        # ExitStack按后进先出顺序关闭资源：Pillow图片→位图→PDF页面。
        # 即使中途编码失败，也会释放已创建的对象，避免反复调试后内存不断增加。
        with ExitStack() as resources:
            logger.debug("event=page_render_start pdf_page=%s dpi=%s", number, dpi)
            page = document[number - 1]  # 用户页码从1开始，PDFium索引从0开始。
            resources.callback(page.close)
            scale = dpi / 72  # PDF页面尺寸使用点（point），每英寸72点。
            width_points, height_points = page.get_size()
            expected_pixels = math.ceil(width_points * scale) * math.ceil(height_points * scale)
            if expected_pixels > self._max_page_pixels:
                raise PdfRenderError(f"PDF第{number}页超过单页像素上限，请降低DPI或调整上限。")
            bitmap = page.render(scale=scale)
            resources.callback(bitmap.close)
            image = bitmap.to_pil()
            resources.callback(image.close)
            # 某些Pillow图片可能共享底层位图内存，必须在关闭bitmap前完成编码。
            with BytesIO() as output:
                image.save(output, format="PNG", dpi=(dpi, dpi))
                logger.debug("event=page_render_result pdf_page=%s width_px=%s height_px=%s output_bytes=%s", number, image.width, image.height, output.tell())
                return PdfPageImage(
                    page_number=number, width_px=image.width, height_px=image.height,
                    png_bytes=output.getvalue(),
                )
