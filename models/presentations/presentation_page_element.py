"""成品页的内容类型；每个元素只携带对应类型的绘制数据。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.presentations.presentation_list_plan import PresentationListPlan
from models.presentations.presentation_table_plan import PresentationTablePlan
from models.presentations.presentation_object_geometry import Color, PresentationBox
from models.presentations.presentation_chart_style import ChartAxisStyle, ChartDisplayStyle


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
    color: Color | None = Field(default=None, description="柱状图系列填充色或折线系列线条色，格式#RRGGBB；不填时沿用Office主题色，饼图使用point_colors。")


class ChartElement(PresentationBox):
    type: Literal["chart"] = Field(description="创建可编辑的原生PPT图表。")
    chart_type: Literal["column", "line", "pie"] = Field(description="图表类型：column柱状、line折线、pie饼图。")
    categories: list[str] = Field(min_length=1, max_length=30, description="分类标签，顺序与每个系列数值一致。")
    series: list[ChartSeries] = Field(min_length=1, max_length=8, description="数据系列；饼图只支持一个系列。")
    point_colors: list[Color] | None = Field(default=None, min_length=1, max_length=30, description="仅用于饼图，每个分类对应一个#RRGGBB颜色，数量须等于分类数；不填时沿用Office主题色。")
    style: ChartDisplayStyle | None = Field(default=None, description="可选的图表标题、图例、数据标签及默认字体；不传沿用Office默认值。")
    category_axis: ChartAxisStyle | None = Field(default=None, description="可选的分类轴样式，仅柱状图/折线图；不得指定数值范围、主间隔或数字格式。")
    value_axis: ChartAxisStyle | None = Field(default=None, description="可选的数值轴样式，仅柱状图/折线图；可设置范围、刻度间隔、标签及网格线。")

    @model_validator(mode="after")
    def validate_chart(self):
        if any(len(item.values) != len(self.categories) for item in self.series):
            raise ValueError("每个图表系列的数值数量必须等于分类数量。")
        if self.chart_type == "pie" and (len(self.series) != 1 or any(v < 0 for v in self.series[0].values) or not any(self.series[0].values)):
            raise ValueError("饼图需要一个非负且至少有一个正数的系列。")
        if self.chart_type == "pie" and any(item.color is not None for item in self.series):
            raise ValueError("饼图扇区颜色请使用point_colors，不支持系列color。")
        if self.point_colors is not None and (self.chart_type != "pie" or len(self.point_colors) != len(self.categories)):
            raise ValueError("point_colors仅用于饼图，数量必须等于分类数量。")
        if self.chart_type == "pie" and (self.category_axis is not None or self.value_axis is not None):
            raise ValueError("饼图没有坐标轴，不能设置坐标轴样式。")
        if self.category_axis is not None and any(value is not None for value in (
            self.category_axis.minimum, self.category_axis.maximum,
            self.category_axis.major_unit, self.category_axis.minor_unit, self.category_axis.number_format,
        )):
            raise ValueError("分类轴不能设置数值范围、刻度间隔或数字格式。")
        return self


class TableElement(PresentationTablePlan):
    type: Literal["table"] = Field(description="可编辑PPT表格，支持两种交替行色。")


class ListElement(PresentationListPlan):
    type: Literal["list"] = Field(description="多项可编辑文字框列表，标记是普通文字。")


PresentationPageElement = Annotated[TextElement | ImageElement | VideoElement | AudioElement | ChartElement | TableElement | ListElement, Field(discriminator="type")]
