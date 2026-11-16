"""原生PPT图表的可选外观；None表示不覆盖Office默认或模板主题。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.presentations.presentation_object_geometry import Color


class ChartAxisStyle(BaseModel):
    """坐标轴可调样式；分类轴不接受数值刻度范围和数值格式。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    visible: bool | None = Field(default=None, description="是否显示整条坐标轴；不传保留Office默认值。")
    title: str | None = Field(default=None, max_length=100, description="轴标题文字；不传不覆盖，空字符串隐藏标题。")
    line_visible: bool | None = Field(default=None, description="是否显示轴线；不传沿用Office默认值。隐藏轴线时不能同时指定轴线颜色或宽度。")
    line_color: Color | None = Field(default=None, description="轴线颜色#RRGGBB；不传沿用主题。")
    line_width: float | None = Field(default=None, gt=0, le=10, description="轴线宽度，单位pt，范围(0,10]；不传保留默认。")
    major_tick: Literal["none", "inside", "outside", "cross"] | None = Field(default=None, description="主要刻度线位置：none/inside/outside/cross；不传保留默认。")
    minor_tick: Literal["none", "inside", "outside", "cross"] | None = Field(default=None, description="次要刻度线位置：none/inside/outside/cross；不传保留默认。")
    label_position: Literal["none", "next_to_axis", "low", "high"] | None = Field(default=None, description="刻度标签位置：none隐藏、next_to_axis靠轴、low低侧、high高侧。")
    label_font_name: str | None = Field(default=None, min_length=1, max_length=100, description="刻度标签字体；缺失字体可能被替换。")
    label_font_size: float | None = Field(default=None, ge=6, le=48, description="刻度标签字号，单位pt，范围6至48。")
    label_color: Color | None = Field(default=None, description="刻度标签颜色#RRGGBB。")
    minimum: float | None = Field(default=None, description="数值轴最小值；仅value_axis有效，None由Office自动决定。")
    maximum: float | None = Field(default=None, description="数值轴最大值；仅value_axis有效，须大于minimum。")
    major_unit: float | None = Field(default=None, gt=0, description="数值轴主刻度间隔，必须大于0；仅value_axis有效。")
    minor_unit: float | None = Field(default=None, gt=0, description="数值轴次刻度间隔，必须大于0；仅value_axis有效。")
    number_format: str | None = Field(default=None, min_length=1, max_length=80, description="数值轴数字格式，例如0、0.0或0%；仅value_axis有效。0%将0.5显示为50%。")
    major_gridlines: bool | None = Field(default=None, description="是否显示主要网格线；不传保留Office默认值。")
    gridline_color: Color | None = Field(default=None, description="主要网格线颜色#RRGGBB；必须同时指定major_gridlines=true。")
    gridline_width: float | None = Field(default=None, gt=0, le=10, description="主要网格线宽度pt；必须同时指定major_gridlines=true。")

    @model_validator(mode="after")
    def validate_axis(self):
        if self.minimum is not None and self.maximum is not None and self.minimum >= self.maximum:
            raise ValueError("坐标轴minimum必须小于maximum。")
        if self.line_visible is False and (self.line_color is not None or self.line_width is not None):
            raise ValueError("隐藏轴线时不能设置轴线颜色或宽度。")
        if (self.gridline_color is not None or self.gridline_width is not None) and self.major_gridlines is not True:
            raise ValueError("配置网格线颜色或宽度时必须设置major_gridlines=true。")
        return self


class ChartDisplayStyle(BaseModel):
    """图表整体文字和图例样式；不传值不覆盖Office默认行为。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, max_length=100, description="图表标题；空字符串隐藏标题，不传保留默认。")
    legend_visible: bool | None = Field(default=None, description="是否显示图例；不传保留Office默认值。")
    legend_position: Literal["bottom", "top", "left", "right"] | None = Field(default=None, description="图例位置；设置位置时必须设置legend_visible=true。")
    data_labels: bool | None = Field(default=None, description="是否显示每个数据点的数值标签；不传保留Office默认值。")
    font_name: str | None = Field(default=None, min_length=1, max_length=100, description="图表默认字体名称；不保证打开设备已安装。")
    font_size: float | None = Field(default=None, ge=6, le=48, description="图表默认字号，单位pt，范围6至48。")

    @model_validator(mode="after")
    def validate_legend(self):
        if self.legend_position is not None and self.legend_visible is not True:
            raise ValueError("设置图例位置时必须设置legend_visible=true。")
        return self
