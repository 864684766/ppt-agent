"""模型提出制作计划，运行时调用注入的PPT生成器。"""

import asyncio

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.presentations.presentation_builder_contract import PresentationBuildError, PresentationBuilder
from models.presentations.build_presentation_contract import BuildPresentationInput, BuildPresentationOutput, PresentationPagePlan


def create_build_presentation_tool(*, builder: PresentationBuilder) -> BaseTool:
    """创建工具，文件与登记由宿主组装；不调用模型或网络。"""
    @tool("build_presentation", args_schema=BuildPresentationInput, description=(
        "根据确认后的页面计划和宿主登记的模板生成PPTX；不搜集资料、不生成大纲或自动决定映射。"
        "pages顺序即成品顺序，每页role是用途标签、source_slide_number是原模板实际页码（从1起），"
        "replacements指定参考页中实际文字框的shape_id及已确认text；支持组合内文字，"
        "elements按type选择text文字、image图片、video视频、audio音频、chart图表、table表格或list列表，可混用并按顺序叠放；"
        "所有新增对象坐标尺寸以英寸计，图片只接受宿主登记的PNG/JPEG编号并按宽高拉伸。"
        "视频MP4、音频MP3由宿主登记并通过实验性接口嵌入，实际播放及兼容性未经验证；视频可指定登记图片为封面。"
        "图表支持柱状、折线和饼图；表格列表不自动拆页，列表标记为普通文字；不自动检查遮挡和溢出。"
        "不支持图片文字、表格单元格或母版文字。未列出的文字会原样保留，可能包含示例内容。"
        "按计划输出新文件，不覆盖模板；复杂资源可能失败，动画及备注不复制，文字样式和溢出需核对。"
        "不做成品8至12页规则及事实、引用或视觉检查，可按需调用check_presentation。"
        "返回template_id原编号、artifact_id新产物编号、file_name文件名、slide_count页数、"
        "pages各页slide_number/source_slide_number/role/replacement_count/element_count，以及warnings限制；"
        "产物编号需宿主登记后才能交给检查工具。"
    ))
    @log_operation("tool.build_presentation")
    async def build_presentation(template_id: str, pages: list[PresentationPagePlan]) -> BuildPresentationOutput:
        try:
            return await asyncio.to_thread(builder.build, template_id=template_id, pages=pages)
        except PresentationBuildError as error:
            raise ToolException(str(error)) from None

    return build_presentation
