"""视觉识别的可替换边界；不依赖LangChain、HTTP、配置或本机文件路径。"""

from typing import Literal, Protocol

from models.templates.template_visual_analysis import TemplateVisualAnalysis


class TemplateVisionError(Exception):
    """可以向调用方展示的识别失败原因，不包含密钥、图片或上游异常原文。"""


class TemplateVisionAnalyzer(Protocol):
    """只约定调用方式，不创建模型；未来可替换供应商而保持调用方不变。"""

    async def analyze(
        self, *, image_bytes: bytes, mime_type: Literal["image/png", "image/jpeg"],
    ) -> TemplateVisualAnalysis:
        """识别一张PNG/JPEG的原始字节，返回视觉判断；失败抛TemplateVisionError。

        图片读取、页面来源关联和模型生命周期由外层负责。本方法不写磁盘，
        不生成预览，不读取环境变量，也不确认图片来自哪一张PPT页面。
        """
        ...
