"""技能发现的LangChain薄入口：异步扫描、纯业务筛选及公开字段组装。"""


import asyncio

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.skills.skill_catalog import filter_skills
from domain.skills.skill_catalog_contract import SkillCatalog, SkillCatalogError
from models.skills.list_skills_contract import ListSkillsInput, ListSkillsOutput, SkillListItem


def create_list_skills_tool(*, catalog: SkillCatalog) -> BaseTool:
    """通过闭包绑定目录能力；不把本机目录作为模型参数，也不执行技能脚本。"""

    @tool("list_skills", args_schema=ListSkillsInput, description=(
        "发现可用的本地技能介绍，可按keyword字面筛选编号、名称或用途；不自动翻译或扩词。"
        "返回items和returned_count；每项含skill_id、name、description（用途）及version（可能为null）。"
        "只读取技能介绍，不检查依赖或执行技能；需要完整SKILL.md时用read_skill传入skill_id。"
    ))
    @log_operation("tool.list_skills")
    async def list_skills(keyword: str = "") -> ListSkillsOutput:
        """文件扫描放入线程，避免阻塞HTTP事件循环；结果不建立全局缓存。"""
        try:
            snapshot = await asyncio.to_thread(catalog.load)
            selected = filter_skills(snapshot, keyword=keyword)
        except (SkillCatalogError, ValueError) as error:
            raise ToolException(str(error)) from None
        items: list[SkillListItem] = []
        for item in selected:
            items.append({
                "skill_id": item.skill_id, "name": item.name,
                "description": item.description, "version": item.version,
            })
        return {"items": items, "returned_count": len(items)}

    return list_skills
