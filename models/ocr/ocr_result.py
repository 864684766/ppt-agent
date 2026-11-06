"""OCR内部返回值；图片的文件来源和文档页码由调用方另行关联。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrTextRegion:
    """图片中检测到的一处文字，不保证恰好对应自然语言的一整行。

    由OCR适配器创建，文件读取器或测试使用。frozen禁止重新赋值，
    polygon_px使用元组而不是可变列表，避免跨模块传递时位置被意外修改。
    """

    # 引擎实际识别的非空文字；没有让语言模型补写、纠错或推测。
    text: str
    # 四边形的四个顶点，各点为(x, y)浮点像素坐标；原点在图片左上角。
    # 使用经过EXIF方向校正后的原图坐标，不是PDF坐标、EMU或0~1比例。
    # 保留引擎顶点顺序，倾斜文字不压缩为轴对齐矩形，不保证点被夹在画布内。
    polygon_px: tuple[tuple[float, float], ...]
    # 引擎的文字识别置信分，范围0~1；不是“内容事实正确”的概率。
    confidence: float


@dataclass(frozen=True)
class OcrResult:
    """一张图片的识别结果；不是Agent工具或HTTP响应，也不包含图片原始字节。"""

    # EXIF方向校正后的图片宽、高，单位像素；polygon_px使用同一坐标空间。
    width_px: int
    height_px: int
    # 引擎返回顺序；不保证复杂分栏、表格的阅读顺序。空元组表示未检出文字。
    regions: tuple[OcrTextRegion, ...]

    @property
    def text(self) -> str:
        """将各区域以换行连接，便于查看；空结果为""，不重复存储一份正文。"""
        return "\n".join(region.text for region in self.regions)
