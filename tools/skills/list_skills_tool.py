"""技能发现的LangChain薄入口：异步扫描、纯业务筛选及公开字段组装。"""

import asyncio

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from domain.skills.skill_catalog import filter_skills
from domain.skills.skill_catalog_contract import SkillCatalog, SkillCatalogError
from models.skills.list_skills_contract import ListSkillsInput, ListSkillsOutput, SkillListItem


def create_list_skills_tool(*, catalog: SkillCatalog) -> BaseTool:
    """通过闭包绑定目录能力；不把本机目录作为模型参数，也不执行技能脚本。"""

    @tool("list_skills", args_schema=ListSkillsInput, description=(
        "需要发现本地有哪些技能、了解其适用场景时使用；不联网、不安装、不执行技能。"
        "可按keyword筛选技能编号、名称、用途说明，省略则列出全部成功读取介绍的技能；不自动翻译或语义扩词。"
        "返回items（技能摘要）和returned_count（本次条数，无分页）。不符合介绍格式的技能记录日志并忽略，不返回给模型。"
        "每项skill_id是技能目录编号，name是声明名称，description是作者的用途说明，version是声明版本或null。"
        "仅扫描并返回SKILL.md的介绍元数据；不检查依赖、不分析脚本或执行流程，也不判断技能可用性。"
        "需要完整指令时后续使用read_skill，该工具尚未实现。当前使用项目内置skills目录，不能传任意本机路径。"
    ))
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
