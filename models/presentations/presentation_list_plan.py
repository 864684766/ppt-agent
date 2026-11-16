"""列表工具输入和公开输出。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.presentations.presentation_object_geometry import Color, PresentationBox


class PresentationListItem(BaseModel):
    """一个列表项，level为视觉缩进层级而非自动编号级别。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=500, description="已确认的列表项文字；不自动生成内容。")
    level: int = Field(default=0, ge=0, le=2, description="缩进层级，0至2，默认0；每级缩进0.3英寸。")


class PresentationListPlan(PresentationBox):
    items: list[PresentationListItem] = Field(min_length=1, max_length=20, description="1至20项，按提供顺序绘制；每项一个独立可编辑文字框。")
    marker: Literal["bullet", "number", "none"] = Field(default="bullet", description="列表标记：bullet显示圆点，number按全列表顺序显示数字，none无标记；标记作为普通文字，不是PPT自动编号。")
    text_color: Color = Field(default="#202A32", description="文字和标记颜色#RRGGBB。")
    font_size: float = Field(default=20, ge=8, le=48, description="字号，单位pt，默认20，范围8至48。")
    font_name: str = Field(default="Microsoft YaHei", min_length=1, max_length=100, description="字体名称；实际效果受打开设备字体影响。")


