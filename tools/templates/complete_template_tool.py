"""模型可调用入口；文件处理由注入的补全器完成。"""

import asyncio

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.templates.template_completer_contract import TemplateCompleter, TemplateCompletionError
from models.templates.complete_template_contract import CompleteTemplateInput, CompleteTemplateOutput, TemplatePagePlan


def create_complete_template_tool(*, completer: TemplateCompleter) -> BaseTool:
    """注入补全实现，创建模型可见工具；不在创建时读取文件。"""
    @tool("complete_template", args_schema=CompleteTemplateInput, description=(
        "模板缺少所需示例页面且已有明确补全计划时使用。template_id是宿主登记编号；"
        "target_slide_count为最终总页数，默认10，范围8至12，包含原页面。"
        "pages每项包含role用途及source_slide_number原模板参考页码（从1开始），"
        "数量必须等于目标页数减原页数，不会自动删页。复制参考页支持的对象和图片，保留原文字；"
        "不复制动画、切换、备注，图表等复杂资源可能失败；不创建新布局、不生成正文。"
        "布局含义或用户偏好不明确时先请求用户确认。"
        "返回template_id原模板编号、output_template_id新模板编号、file_name文件名、"
        "original_slide_count原页数、slide_count新总页数、added_pages新增页的role/source_slide_number/slide_number、"
        "warnings限制；输出编号尚需宿主登记。保存新文件，不覆盖原模板，结果需人工核对。"
    ))
    @log_operation("tool.complete_template")
    async def complete_template(template_id: str, pages: list[TemplatePagePlan], target_slide_count: int = 10) -> CompleteTemplateOutput:
        try:
            return await asyncio.to_thread(completer.complete, template_id=template_id, target_slide_count=target_slide_count, pages=pages)
        except TemplateCompletionError as error:
            raise ToolException(str(error)) from None

    return complete_template
