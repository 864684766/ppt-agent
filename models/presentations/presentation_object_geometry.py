"""表格与列表共享的画布范围和颜色字段。"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$", description="RGB颜色，格式#RRGGBB，例如#FFFFFF。")]


class PresentationBox(BaseModel):
    """坐标从幻灯片左上角开始，所有位置和尺寸的单位均为英寸。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    x: float = Field(ge=0, description="对象左侧距幻灯片左边的距离，单位英寸。")
    y: float = Field(ge=0, description="对象顶部距幻灯片上边的距离，单位英寸。")
    width: float = Field(gt=0, description="对象宽度，单位英寸，必须位于幻灯片内。")
    height: float = Field(gt=0, description="对象高度，单位英寸，必须位于幻灯片内；不能保证文字实际不会溢出。")
