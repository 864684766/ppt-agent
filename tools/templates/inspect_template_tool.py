"""向模型暴露模板结构检查，实际文件由宿主登记和绑定。"""


import asyncio

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.templates.template_inspector_contract import TemplateInspectionError, TemplateInspector
from models.templates.inspect_template_contract import InspectTemplateInput, InspectTemplateOutput


def create_inspect_template_tool(*, inspector: TemplateInspector) -> BaseTool:
    """闭包注入解析器；模型选编号，解析在工作线程执行，不阻塞HTTP事件循环。"""

    @tool("inspect_template", args_schema=InspectTemplateInput, description=(
        "读取已登记PPTX模板的结构，寻找实际页面、版式、母版及文字对象；不修改文件。"
        "返回文件指纹、页数、尺寸、slides（实际页）、layouts（版式）、masters（母版）和warnings（限制）。"
        "页面编号从1开始；尺寸和坐标单位为EMU（914400 EMU=1英寸），几何值null表示未解析。"
        "shapes包含对象编号、类型、坐标、占位符、文本、表格和children；组合子对象使用group坐标，z_order是绘制顺序。"
        "版式和母版文本可能是编辑提示，不一定是实际页面正文；不自动展开继承样式。"
        "不执行OCR或视觉识别，也不判断封面等页面角色；角色不明确时需要进一步分析或询问用户。"
    ))
    @log_operation("tool.inspect_template")
    async def inspect_template(template_id: str) -> InspectTemplateOutput:
        """结构事实已是公开契约；显式展开以返回普通字典，不传SDK对象。"""
        try:
            result = await asyncio.to_thread(inspector.inspect, template_id=template_id)
        except TemplateInspectionError as error:
            raise ToolException(str(error)) from None
        return {**result}

    return inspect_template
