"""成品页的内容类型；每个元素只携带对应类型的绘制数据。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.presentations.presentation_list_plan import PresentationListPlan
from models.presentations.presentation_table_plan import PresentationTablePlan
from models.presentations.presentation_object_geometry import Color, PresentationBox


class TextElement(PresentationBox):
    type: Literal["text"] = Field(description="普通可编辑文字框。")
    text: str = Field(max_length=4000, description="已确认的文字内容，允许为空。")
    font_name: str = Field(default="Microsoft YaHei", min_length=1, max_length=100, description="字体名，打开端缺失时可能替换。")
    font_size: float = Field(default=20, ge=8, le=48, description="字号，单位pt。")
    color: Color = Field(default="#202A32", description="文字颜色#RRGGBB。")


class ImageElement(PresentationBox):
    type: Literal["image"] = Field(description="已登记图片，按给定宽高拉伸插入。")
    image_id: str = Field(min_length=1, max_length=200, description="宿主已登记的PNG或JPEG图片编号，不是路径或URL。")


class VideoElement(PresentationBox):
    type: Literal["video"] = Field(description="嵌入用户提供的MP4视频；实际播放依赖Office软件和编解码器。")
    video_id: str = Field(min_length=1, max_length=200, description="宿主登记的MP4视频编号，不是路径或URL。")
    poster_image_id: str | None = Field(default=None, description="可选宿主登记PNG/JPEG封面编号；不提供时由python-pptx使用默认媒体图标，不自动截取视频帧。")


class AudioElement(PresentationBox):
    type: Literal["audio"] = Field(description="实验性嵌入用户提供的MP3；播放兼容性须用WPS或PowerPoint人工验证。")
    audio_id: str = Field(min_length=1, max_length=200, description="宿主登记的MP3音频编号，不是路径或URL。")


class ChartSeries(BaseModel):
    """图表一个数值系列；值的顺序对应分类顺序。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100, description="数据系列名称，例如2025年。")
    values: list[float] = Field(min_length=1, max_length=30, description="各分类对应的数值，须为有限数字。")


class ChartElement(PresentationBox):
    type: Literal["chart"] = Field(description="创建可编辑的原生PPT图表。")
    chart_type: Literal["column", "line", "pie"] = Field(description="图表类型：column柱状、line折线、pie饼图。")
    categories: list[str] = Field(min_length=1, max_length=30, description="分类标签，顺序与每个系列数值一致。")
    series: list[ChartSeries] = Field(min_length=1, max_length=8, description="数据系列；饼图只支持一个系列。")

    @model_validator(mode="after")
    def validate_chart(self):
        if any(len(item.values) != len(self.categories) for item in self.series):
            raise ValueError("每个图表系列的数值数量必须等于分类数量。")
        if self.chart_type == "pie" and (len(self.series) != 1 or any(v < 0 for v in self.series[0].values) or not any(self.series[0].values)):
            raise ValueError("饼图需要一个非负且至少有一个正数的系列。")
        return self


class TableElement(PresentationTablePlan):
    type: Literal["table"] = Field(description="可编辑PPT表格，支持两种交替行色。")


class ListElement(PresentationListPlan):
    type: Literal["list"] = Field(description="多项可编辑文字框列表，标记是普通文字。")


PresentationPageElement = Annotated[TextElement | ImageElement | VideoElement | AudioElement | ChartElement | TableElement | ListElement, Field(discriminator="type")]
