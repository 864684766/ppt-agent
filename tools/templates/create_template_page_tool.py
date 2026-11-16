"""面向模型的页面创建工具；由注入的实现处理文件。"""

import asyncio

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.templates.template_page_creator_contract import TemplatePageCreationError, TemplatePageCreator
from models.templates.create_template_page_contract import CreateTemplatePageInput, CreateTemplatePageOutput, PageElement


def create_template_page_tool(*, creator: TemplatePageCreator) -> BaseTool:
    """创建工具入口；用户意图和设计方案由Agent决定。"""
    @tool("create_template_page", args_schema=CreateTemplatePageInput, description=(
        "有明确设计方案时，在已登记PPTX模板追加一页可编辑页面；不调用模型、不自动提取风格。"
        "layout_id来自同一模板inspect_template结果；背景是纯色，elements仅支持文字框和矩形，"
        "坐标尺寸单位英寸、字号单位pt，对象按顺序叠放，超出页面则失败。"
        "版式可能带占位符和母版装饰；不支持图片、图表、动画或自动检测文字溢出。"
        "结果template_id为原编号，output_template_id为新编号，file_name为文件名，"
        "slide_number为新增页码（从1起），element_count为绘制数量，warnings为限制。"
        "新编号需宿主登记；页面视觉效果需人工核对。需求不明确先询问用户。"
    ))
    @log_operation("tool.create_template_page")
    async def create_template_page(template_id: str, layout_id: str, background_color: str,
                                   elements: list[PageElement]) -> CreateTemplatePageOutput:
        try:
            return await asyncio.to_thread(creator.create, template_id=template_id, layout_id=layout_id,
                                           background_color=background_color, elements=elements)
        except TemplatePageCreationError as error:
            raise ToolException(str(error)) from None

    return create_template_page
