"""read_material的LangChain薄入口：绑定快照、调用业务读取、选择公开字段。"""


from collections.abc import Sequence

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.materials.material_reader import read_project_material
from domain.materials.material_validator import validate_material_content_data
from models.materials.material_fragment import MaterialFragment
from models.materials.material_source import MaterialSummary
from models.materials.read_material_contract import ReadMaterialInput, ReadMaterialOutput


def create_read_material_tool(
    *, project_id: str, materials: Sequence[MaterialSummary],
    fragments: Sequence[MaterialFragment],
) -> BaseTool:
    """宿主绑定项目与不可变快照；资料更新后需重建工具。

    组装数据不合法抛ValueError；执行时的业务错误转为ToolException。
    不创建仓库、不读取环境变量，也不持有需要释放的文件/网络连接。
    """
    material_snapshot = tuple(materials)
    fragment_snapshot = tuple(fragments)
    validate_material_content_data(
        project_id=project_id, materials=material_snapshot, fragments=fragment_snapshot,
    )

    @tool("read_material", args_schema=ReadMaterialInput, description=(
        "读取已登记且ready资料中的一个已解析正文块，用于核实原文或补读search_materials截断内容。"
        "使用搜索结果提供的source_id、version和block_id定位，不要猜测；不联网或直接打开文件。"
        "返回text、location、offset、end_offset、total_chars和next_offset；偏移按字符计，范围为[offset,end_offset)。"
        "next_offset可用于续读，null表示到块尾；一个块不是整份资料。"
    ))
    @log_operation("tool.read_material")
    def read_material(
        source_id: str, version: str, block_id: str,
        offset: int = 0, max_chars: int = 2000,
    ) -> ReadMaterialOutput:
        """参数说明来自ReadMaterialInput；闭包提供项目和快照，不交给模型选择。"""
        try:
            result = read_project_material(
                project_id=project_id, materials=material_snapshot, fragments=fragment_snapshot,
                source_id=source_id, version=version, block_id=block_id,
                offset=offset, max_chars=max_chars,
            )
        except ValueError as error:
            raise ToolException(str(error)) from None

        # 只选择约定公开字段，不把内部project_id或原对象整体交给模型。
        fragment = result.fragment
        return {
            "source_id": fragment.source_id, "version": fragment.version,
            "location": {"block_id": fragment.block_id, "page": fragment.page},
            "text": result.text, "offset": result.offset, "end_offset": result.end_offset,
            "total_chars": len(fragment.text), "next_offset": result.next_offset,
        }

    return read_material
