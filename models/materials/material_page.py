"""业务查询结果：一页内部资料目录，不是模型工具的公开输出。

items 中的 MaterialSummary 包含 project_id；对外结果由工具另外选择
公开字段，因此 MaterialPage 与 ListMaterialsOutput 不应混为同一个类型。
"""

from dataclasses import dataclass

from models.materials.material_summary import MaterialSummary


@dataclass(frozen=True, slots=True)
class MaterialPage:
    """筛选后的目录页；total 为筛选后总数，next_offset 为下一页偏移。"""

    items: tuple[MaterialSummary, ...]
    total: int
    next_offset: int | None

