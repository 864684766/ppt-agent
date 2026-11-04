"""read_skill的LangChain入口，读取能力通过协议注入。"""

import asyncio

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from domain.skills.skill_reader_contract import SkillReadError, SkillReader
from models.skills.read_skill_contract import ReadSkillInput, ReadSkillOutput


def create_read_skill_tool(*, reader: SkillReader) -> BaseTool:
    """闭包保存宿主提供的读取器，模型只传skill_id，不选择根目录。"""

    @tool("read_skill", args_schema=ReadSkillInput, description=(
        "选中list_skills中的技能后，使用本工具读取该技能SKILL.md完整指令。"
        "返回skill_id（选中的技能编号）、resource_path（技能内文件标识，恒为SKILL.md）、"
        "content（包含YAML头部的完整Markdown文本，不截断）。"
        "仅读取入口文件，不自动读取参考资料、不解释依赖、不执行脚本，也不保证技能适配当前运行时。"
        "技能不规范或无法读取时记录日志并报错，不返回虚构内容；可重新发现或选择其他技能。"
        "附属资源读取及技能执行尚未接线；读取成功不表示已执行技能。"
    ))
    async def read_skill(skill_id: str) -> ReadSkillOutput:
        """线程执行本地读取以避免阻塞事件循环，公开错误转换为ToolException。"""
        try:
            content = await asyncio.to_thread(reader.read, skill_id=skill_id)
        except SkillReadError as error:
            raise ToolException(str(error)) from None
        return {"skill_id": skill_id, "resource_path": "SKILL.md", "content": content}

    return read_skill
