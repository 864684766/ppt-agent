"""search_materials的LangChain入口：绑定快照、执行查询并选择公开字段。"""


from collections.abc import Sequence
from typing import Literal

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
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
            "在已登记且ready的资料正文中查找关键词，不联网、不解析文件。"
            "多个queries任一命中即可，按字面匹配并忽略大小写，不自动扩词；结果不是相关性排序。"
            "返回matches（含source_id、version、location、matched_queries、text及text_truncated）、total_matches和truncated。"
            "location包含block_id和页码page（从1开始或null）；需要完整上下文时用read_material读取该块。"
            "matched_queries针对完整块，截取文本中可能看不到全部关键词；无命中不代表资料中不存在相关结论。"
        ),
    )
    @log_operation("tool.search_materials")
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
