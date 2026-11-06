"""check_presentation薄适配：模型选择产物编号，实际检查在工作线程执行。"""

import asyncio
from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.presentations.presentation_checker_contract import PresentationChecker, PresentationCheckError
from models.presentations.check_presentation_contract import CheckPresentationInput, CheckPresentationOutput


def create_check_presentation_tool(*, checker: PresentationChecker) -> BaseTool:
    """闭包保留宿主注入的检查器；创建工具不读文件、不加载PPT或模型。"""
    @tool("check_presentation", args_schema=CheckPresentationInput, description=(
        "需要检查已生成或宿主登记的PPTX时使用，只读、不修复文件。输入artifact_id为宿主产物编号，不是路径。"
        "实际检查文件大小、Office包基础结构、python-pptx可解析性、宿主页数范围和无可提取文字页。"
        "返回artifact_id、file_name（展示名）、sha256（字节指纹）、size_bytes（实际字节数）及slide_count（页数）；"
        "超限未读完整时指纹/大小为null，未解析时页数为null。"
        "checks各项含rule_id（规则名）、status（pass/fail/warning/not_checked）、required（本轮必过）、"
        "message（安全说明）、expected（要求）、actual（实际值，未知null）、slide_numbers（相关页码，从1开始）。"
        "passed仅代表所有required规则通过，不能把not_checked当通过。"
        "无可提取文字只给warning：图片页可能合法，不做OCR。"
        "当前大纲覆盖、来源核查、排版和Office真实打开均not_checked；"
        "包结构通过不证明所有关系完整、文字无溢出、事实准确或美观。"
        "页数/限额由宿主固定，模型不能修改要求以让失败变成功；失败应按具体规则处理。"
    ))
    @log_operation("tool.check_presentation")
    async def check_presentation(artifact_id: str) -> CheckPresentationOutput:
        """把同步文件/解析工作移到线程；取消等待不保证立即终止底层操作。"""
        try:
            return await asyncio.to_thread(checker.check, artifact_id=artifact_id)
        except PresentationCheckError as error:
            raise ToolException(str(error)) from None

    return check_presentation
