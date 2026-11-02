"""search_materials的LangChain入口：绑定快照、执行查询并选择公开字段。"""

from collections.abc import Sequence
from typing import Literal

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from domain.materials.material_search import search_project_materials
from domain.materials.material_validator import validate_material_content_data
from models.materials.material_fragment import MaterialFragment
from models.materials.material_source import MaterialSummary
from models.materials.search_materials_contract import (
    MaterialSearchItem,
    SearchMaterialsInput,
    SearchMaterialsOutput,
)


def create_search_materials_tool(
    *, project_id: str, materials: Sequence[MaterialSummary],
    fragments: Sequence[MaterialFragment],
) -> BaseTool:
    """由宿主绑定项目、目录和正文；不是让模型传入全文或选择项目。

    复制成不可变快照，不创建全局内存仓库。正文和目录更新后需重建。
    组装数据错误抛ValueError；执行时业务错误转ToolException交运行时处理。
    无网络、文件和模型连接需要释放；不读取Settings或.env。
    """
    material_snapshot = tuple(materials)
    fragment_snapshot = tuple(fragments)
    validate_material_content_data(
        project_id=project_id, materials=material_snapshot, fragments=fragment_snapshot,
    )

    @tool(
        "search_materials",
        args_schema=SearchMaterialsInput,
        description=(
            "需要在当前项目已登记且ready的正文中定位关键词和引用来源时使用。"
            "多个queries按任意一个命中，字面匹配、忽略大小写；不自动扩词、"
            "不访问互联网、不解析文件。返回matches及total_matches、truncated；"
            "每项包含source_id、version、location(block_id及从1开始或null的page)、"
            "matched_queries、text及text_truncated。matched_queries针对完整原文块，"
            "可能不都出现在截取文本中。结果截断或需核实上下文时，应缩小查询或后续读取原块。"
            "排序按来源/页码/块ID，不是相关性排名；没有命中不代表资料结论不存在。"
            "不存在、未ready或正文未载入会明确报错，与空matches不同。"
        ),
    )
    def search_materials(
        queries: list[str], source_ids: list[str] | None = None,
        origin: Literal["all", "uploaded", "web"] = "all",
        max_results: int = 10, max_chars_per_match: int = 300,
    ) -> SearchMaterialsOutput:
        """查询已绑定正文；项目与数据来自闭包，不是模型调用参数。

        具体参数说明由SearchMaterialsInput生成Schema。工具只适配业务结果，
        不把完整MaterialFragment（包含内部project_id）直接交给模型。
        """
        try:
            result = search_project_materials(
                project_id=project_id, materials=material_snapshot, fragments=fragment_snapshot,
                queries=queries, source_ids=source_ids, origin=origin,
                max_results=max_results, max_chars_per_match=max_chars_per_match,
            )
        except ValueError as error:
            # 业务层只产生固定公开提示，不透传文件/网络异常或敏感内容。
            raise ToolException(str(error)) from None

        matches: list[MaterialSearchItem] = []
        # 使用显式循环，便于初学者逐步打断点观察每条结果的组装。
        for match in result.matches:
            block = match.fragment
            matches.append({
                "source_id": block.source_id,
                "version": block.version,
                "location": {"block_id": block.block_id, "page": block.page},
                "matched_queries": list(match.matched_queries),
                "text": match.text,
                "text_truncated": match.text_truncated,
            })
        return {
            "matches": matches,
            "total_matches": result.total_matches,
            "truncated": result.truncated,
        }

    return search_materials
