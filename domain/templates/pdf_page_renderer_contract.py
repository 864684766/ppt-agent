"""PDF页面渲染接口，业务调用方无需依赖PDFium或Pillow。"""

from collections.abc import Sequence
from typing import Protocol

from models.templates.pdf_page_image import PdfRenderResult


class PdfRenderError(RuntimeError):
    """可公开的渲染失败原因；不返回PDF正文、密码或底层库异常原文。"""


class PdfPageRenderer(Protocol):
    """同步渲染接口：这是本地CPU工作，不是网络或模型调用。"""

    def render(
        self, *, pdf_bytes: bytes, pages: Sequence[int] | None = None, dpi: int = 144,
    ) -> PdfRenderResult:
        """读取PDF并渲染所选页面，失败抛PdfRenderError。

        pdf_bytes：原始PDF文件字节，必填且非空；不接收路径。
        pages：从1开始的页码序列，例如[1, 3]；None表示全部页。
        空列表、重复页码、非整数或超出总页数均报错；保留用户指定顺序。
        dpi：整数36–300，默认144；每页还受实现的像素上限限制。
        返回文件指纹、PDF总页数、DPI及所选页图片，不写磁盘或调用视觉模型。
        """
        ...
