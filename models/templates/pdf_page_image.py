"""PDF渲染的内部结果；不含磁盘路径、Agent框架或PPT页码推测。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PdfPageImage:
    """一张PDF页面对应的PNG。frozen=True禁止重新赋值字段，避免页码被误改。"""

    # 原PDF中的页码，从1开始；不是模型判断的页码，也不自动等同于PPT页码。
    page_number: int
    # PNG的实际宽度，单位像素（px），不是PPT使用的EMU。
    width_px: int
    # PNG的实际高度，单位像素（px）。
    height_px: int
    # PNG完整文件字节，可由调用方落盘或传给视觉模块；不包含base64前缀。
    png_bytes: bytes


@dataclass(frozen=True)
class PdfRenderResult:
    """一次调用的结果。创建方是渲染器，使用方是测试或后续页面分析流程。"""

    # 本次输入PDF的SHA-256指纹，用于区分不同文件；不是版本管理或真实性证明。
    pdf_sha256: str
    # 原PDF总页数；即使只渲染两页，这里仍表示原文件全部页数。
    total_pages: int
    # 本次使用的DPI（每英寸像素数），默认144；越高图片通常越大，不保证识别更准。
    dpi: int
    # 按调用方指定的页码顺序保存；pages=None时按PDF原始顺序保存全部页。
    # tuple是元组，不提供append；图片字节和元组均不可变，适合跨层传递。
    images: tuple[PdfPageImage, ...]
