"""表格工具输入和公开输出。"""

from pydantic import Field, model_validator

from models.presentations.presentation_object_geometry import Color, PresentationBox


class PresentationTablePlan(PresentationBox):
    """第一行为表头；行列必须对齐，内容为已确认的纯文本。"""

    headers: list[str] = Field(min_length=1, max_length=8, description="表头列表，1至8列；每列一个标题，内容由调用方确认。")
    rows: list[list[str]] = Field(min_length=1, max_length=20, description="1至20个数据行，每行字符串数量必须等于表头列数；不支持合并单元格。")
    header_color: Color = Field(default="#2948AA", description="表头背景色#RRGGBB，默认#2948AA。")
    header_text_color: Color = Field(default="#FFFFFF", description="表头文字颜色#RRGGBB，默认白色。")
    row_colors: list[Color] = Field(default_factory=lambda: ["#FFFFFF", "#EDF2F7"], min_length=2, max_length=2, description="两种数据行背景色，按顺序交替形成斑马条纹，例如白色与浅灰蓝色。")
    text_color: Color = Field(default="#202A32", description="数据单元格文字颜色#RRGGBB。")
    font_size: float = Field(default=16, ge=8, le=48, description="表头和正文的字号，单位pt，默认16，允许8至48。")
    font_name: str = Field(default="Microsoft YaHei", min_length=1, max_length=100, description="字体名称；打开设备未安装时可能替换。")

    @model_validator(mode="after")
    def check_rows(self):
        """在工具边界明确拒绝列数不匹配和过长的单元格。"""
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("每个数据行的列数必须与表头一致。")
        if any(len(text) > 500 for text in [*self.headers, *(cell for row in self.rows for cell in row)]):
            raise ValueError("单元格文字最多500字符。")
        return self


