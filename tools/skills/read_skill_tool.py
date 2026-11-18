"""read_skill的LangChain入口，读取能力通过协议注入。"""


import asyncio

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.skills.skill_reader_contract import SkillReadError, SkillReader
from models.skills.read_skill_contract import ReadSkillInput, ReadSkillOutput


def create_read_skill_tool(*, reader: SkillReader) -> BaseTool:
    """闭包保存宿主提供的读取器，模型只传skill_id，不选择根目录。"""

    @tool("read_skill", args_schema=ReadSkillInput, description=(
        "使用list_skills返回的skill_id读取技能SKILL.md完整指令。"
        "返回skill_id、resource_path（SKILL.md）和content（含YAML头部的完整Markdown）。"
        "只读取入口文件，不自动读取附属资料或执行脚本；读取成功不代表技能已执行或依赖可用。"
    ))
    @log_operation("tool.read_skill")
    async def read_skill(skill_id: str) -> ReadSkillOutput:
        """线程执行本地读取以避免阻塞事件循环，公开错误转换为ToolException。"""
        try:
            content = await asyncio.to_thread(reader.read, skill_id=skill_id)
        except SkillReadError as error:
            raise ToolException(str(error)) from None
        return {"skill_id": skill_id, "resource_path": "SKILL.md", "content": content}

    return read_skill
