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
        "需要了解PPTX模板结构、寻找可用版式和文字槽位时使用。只读宿主登记的template_id。"
        "返回template_id、file_name（文件名）、sha256（内容指纹）、slide_count（样例页数）、"
        "slide_width_emu/slide_height_emu（页面尺寸，914400 EMU=1英寸）。"
        "slides含slide_id、slide_number（从1起的页序）、layout_id和shapes；"
        "layouts含layout_id/name/master_id/shapes，masters含master_id/layout_ids/shapes。"
        "slides是实际页面，layouts是可复用排版定义，masters是管理版式的上层设计；"
        "三者数量无需相同，多页可共用同一版式；master.layout_ids条数是版式数，不是母版数。"
        "对象包含object_id（同文件内定位）、shape_id/name/shape_type/z_order、"
        "left_emu/top_emu/width_emu/height_emu、rotation_degrees、coordinate_space、"
        "is_placeholder/placeholder_idx/placeholder_type、text、table_rows、children。"
        "name是内部对象名，不是可见正文；text是自身存储文本，母版/版式可能含编辑提示，不能当作页面正文；"
        "None表示无文本框；children为组合子对象，坐标为group空间，未换算绝对位置；"
        "顶层坐标为slide空间。几何值None表示未解析，不代表0；z_order是绘制顺序，不是阅读顺序。"
        "页、版式、母版对象分别返回，不自动平铺继承样式。warnings说明提取限制。"
        "不做OCR或视觉分析，不展开图表数据、SmartArt、背景与主题字体；不判断封面/目录等角色，"
        "不得只按页序或版式名确定角色；不确定时应请求用户指导。不修改文件，不生成预览。"
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
