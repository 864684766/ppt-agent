"""inspect_template工具的输入和公开输出，共享模板结构定义避免重复实体。"""

from pydantic import BaseModel, ConfigDict, Field

from models.templates.template_structure import TemplateStructure


class InspectTemplateInput(BaseModel):
    """只允许选择宿主登记的模板，不传电脑路径。"""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    template_id: str = Field(min_length=1, max_length=200, description=(
        "必填，宿主提供的模板编号，例如company-template；不是文件路径或页码。"
        "只能选择本次登记的模板；一次读取其全部样例页、母版和版式，不修改文件。"
    ))


class InspectTemplateOutput(TemplateStructure):
    """公开结果沿用共享结构事实；没有额外内部字段需要剔除。"""
