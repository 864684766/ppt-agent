"""公共OCR协议：调用方只需要图片字节和统一结果，不需要知道引擎品牌。"""

from typing import Protocol

from models.ocr.ocr_result import OcrResult


class OcrError(RuntimeError):
    """安全的识别失败说明，不包含原始图片、正文或第三方异常原文。"""


class ImageTextRecognizer(Protocol):
    """同步CPU能力；在异步HTTP中使用时，调用方负责放到工作线程执行。"""

    def recognize(self, *, image_bytes: bytes) -> OcrResult:
        """识别单张图片，返回文字区域、位置、置信分和校正后像素尺寸。

        image_bytes是图片完整文件字节，不是路径、URL、base64或PDF。
        输入字节仍归调用方；实现关闭自己解码的图片，不保存原文件。
        格式、大小、引擎或模型错误抛OcrError；合法空白图片可返回空结果。
        页码、来源ID、文件名称由调用方关联，OCR不负责文档解析或语义判断。
        """
        ...
