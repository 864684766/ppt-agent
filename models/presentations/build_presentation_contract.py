"""生成PPT工具的输入方案与结果；页面内容由调用方事先确认。"""

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field

from models.presentations.presentation_page_element import PresentationPageElement


class TextReplacement(BaseModel):
    """将某个实际页的文本框整体替换为已确认的文字。"""

    model_config = ConfigDict(extra="forbid")
    shape_id: int = Field(ge=1, description="原模板参考页内文字对象的shape_id，可通过inspect_template的shapes及children查看，不是版式或母版对象。")
    text: str = Field(max_length=4000, description="要写入该文字框的已确认文字；允许空字符串清空示例文字。不会自动核对事实或生成正文。")


class PresentationPagePlan(BaseModel):
    """成品中的一页，pages列表的顺序就是成品顺序。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    role: str = Field(min_length=1, max_length=40, description="页面用途标签，例如封面、目录、内容页、来源页；仅报告用途，不自动判断或生成。")
    source_slide_number: int = Field(ge=1, description="原模板实际参考页页码，从1开始，不是母版或版式编号。")
    replacements: list[TextReplacement] = Field(max_length=100, description="此页明确要替换的文字对象列表；未列出的对象保留模板原文字，可能是示例内容，需调用方检查。")
    elements: list[PresentationPageElement] = Field(default_factory=list, max_length=30, description="新增元素列表：text文字、image图片、video视频、audio音频、chart图表、table表格、list列表；按顺序绘制，坐标尺寸单位英寸。")


class BuildPresentationInput(BaseModel):
    """宿主登记模板后，模型提供最终页面顺序及文字映射。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    template_id: str = Field(min_length=1, max_length=200, description="宿主登记的模板编号，不是本机路径或URL。")
    pages: list[PresentationPagePlan] = Field(min_length=1, max_length=100, description="已确认的成品页面计划，按列表顺序生成；至少1页，最多100页为资源上限，不代表通过8至12页成品质检。")


class BuiltPresentationPage(TypedDict):
    # 成品页码从1开始；参考页码也是原模板中从1开始的页码。
    slide_number: int
    source_slide_number: int
    # 用途是调用方提供的标签，替换数量是实际写入的文字框数。
    role: str
    replacement_count: int
    # 成功新增的顶层绘制方案数量；列表方案内部可创建多个文字框。
    element_count: int


class BuildPresentationOutput(TypedDict):
    # 原模板编号与新产物编号；新编号需要宿主登记给检查工具。
    template_id: str
    artifact_id: str
    # 新PPTX的文件名，不含宿主路径。
    file_name: str
    # 成品实际页数与逐页计划结果，顺序一致。
    slide_count: int
    pages: list[BuiltPresentationPage]
    # 文字样式、未替换内容和Office打开等限制提示。
    warnings: list[str]
