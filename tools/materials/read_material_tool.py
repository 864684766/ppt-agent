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
        "已知来源、版本和正文块ID，需要核实原文或补读search_materials截断文本时使用。"
        "读取当前项目ready资料的一个已解析正文块，上传文件与已登记网页均可用；"
        "不联网、不打开原文件、不解析或OCR，不自动包含相邻块。"
        "定位使用source_id、version和block_id，不要猜测块ID。"
        "返回原文text、来源版本、location(block_id/page)、offset、end_offset、"
        "total_chars和next_offset；实际范围为[offset,end_offset)，单位为Python字符。"
        "长块用next_offset续读，null表示到块尾；完整块不等于整份文件。"
        "来源未登记、未ready、版本过期或块不存在会报错，不伪装为空结果。"
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
