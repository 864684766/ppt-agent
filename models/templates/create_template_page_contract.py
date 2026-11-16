"""创建模板页面的输入、绘制方案和公开结果。"""

from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field


Color = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$", description="RGB颜色，格式为#RRGGBB，例如#FFFFFF。")]


class PageElement(BaseModel):
    """一个可编辑对象；位置和尺寸从页面左上角起算，单位均为英寸。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    kind: Literal["text", "rectangle"] = Field(description="对象类型：text文字框，rectangle矩形。")
    x: float = Field(ge=0, description="左边缘距页面左侧的距离，单位英寸，不能为负。")
    y: float = Field(ge=0, description="上边缘距页面顶部的距离，单位英寸，不能为负。")
    width: float = Field(gt=0, description="对象宽度，单位英寸，必须大于0。")
    height: float = Field(gt=0, description="对象高度，单位英寸，必须大于0。")
    color: Color = Field(description="text表示字体颜色，rectangle表示填充颜色，格式#RRGGBB。")
    text: str = Field(default="", max_length=1000, description="文字框内容；rectangle必须为空。建议使用模板示例文字，不填未经确认的业务正文。")
    font_size: float = Field(default=24, ge=6, le=96, description="文字字号，单位pt，默认24，允许6至96；矩形忽略此值。")
    font_name: str = Field(default="Arial", min_length=1, max_length=100, description="文字字体名称，默认Arial；效果取决于打开文件的电脑是否安装字体，矩形忽略。")


class CreateTemplatePageInput(BaseModel):
    """模型给出宿主登记模板、原有版式和明确绘制方案。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    template_id: str = Field(min_length=1, max_length=200, description="宿主登记的模板编号，不是文件路径或URL。")
    layout_id: str = Field(min_length=1, max_length=200, description="所选模板已有版式的layout_id，从inspect_template获取；新增页会继承其母版设计和可见对象。")
    background_color: Color = Field(description="新页面纯色背景，格式#RRGGBB；会覆盖该页继承背景，但不会移除母版上的装饰对象。")
    elements: list[PageElement] = Field(min_length=1, max_length=30, description="按绘制顺序排列的1至30个对象；后画的对象覆盖前面的对象。坐标与尺寸均为英寸。")


class CreateTemplatePageOutput(TypedDict):
    # 原模板和新文件的宿主编号；新编号尚未自动注册。
    template_id: str
    output_template_id: str
    # 新文件名称，不包含路径。
    file_name: str
    # 新页面在输出文件中的页码，从1开始，追加在最后。
    slide_number: int
    # 成功创建的文字框与矩形数量。
    element_count: int
    # 需要用户注意的显示、资源及交付限制。
    warnings: list[str]
