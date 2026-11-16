"""模板补全工具的模型输入和公开结果；TypedDict仅描述结构，不执行校验。"""

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class TemplatePagePlan(BaseModel):
    """一条明确的补页计划，参考页使用原模板中从1开始的页码。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    role: str = Field(min_length=1, max_length=40, description="新增页面的用途，例如目录页或来源页；仅作为报告标签，不自动判断版式。")
    source_slide_number: int = Field(ge=1, description="原模板中用于复制样式的实际幻灯片页码，从1开始；根据模板分析选择，不是母版或版式编号。")


class CompleteTemplateInput(BaseModel):
    """由模型提出模板编号和明确补页计划；文件路径由宿主管理。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    template_id: str = Field(min_length=1, max_length=200, description="宿主登记的原模板编号，不是本机路径或URL。")
    target_slide_count: int = Field(default=10, ge=8, le=12, description="补全后的总页数，包含原有及新增幻灯片，默认10，可设8至12；原模板页数超过目标时不会删页。")
    pages: list[TemplatePagePlan] = Field(min_length=1, max_length=12, description="新增页面计划，按顺序追加；数量必须恰好等于目标总页数减原模板页数，每项指定用途和参考页。")


class CompletedTemplatePage(TypedDict):
    # 用途由调用方指定，不代表工具验证了页面是否符合该用途。
    role: str
    # 用于复制的原模板实际页面页码，从1开始。
    source_slide_number: int
    # 新增页面的实际页码，从1开始。
    slide_number: int


class CompleteTemplateOutput(TypedDict):
    # 原模板登记编号；不暴露本地路径。
    template_id: str
    # 本次新文件的宿主登记编号，可供后续宿主登记使用；当前不自动接入其他工具。
    output_template_id: str
    # 输出文件名，不包含目录。
    file_name: str
    # 处理前与处理后的实际幻灯片总数，包含隐藏页。
    original_slide_count: int
    slide_count: int
    # 按计划顺序新增的页面及其用途和版式。
    added_pages: list[CompletedTemplatePage]
    # 本次能力限制，提醒调用者核对样式和实际打开效果。
    warnings: list[str]
